"""Active search service for the ingestion pipeline.

Supports multiple search providers:
- rss: Google News / custom RSS feeds (original)
- chinese: Chinese web sources (Bing CN, search engines)
- Custom providers added via configuration
"""

from __future__ import annotations

import html
import json
import re
import xml.etree.ElementTree as ET
from email.utils import parsedate_to_datetime
from typing import Dict, Iterable, List, Set
from urllib.error import HTTPError, URLError
from urllib.parse import quote_plus, urlparse
from urllib.request import Request, urlopen

from ..config import Config


class ActiveSearchUnavailable(RuntimeError):
    """Raised when no configured provider can return data."""


# ── Chinese search source templates ──────────────────────────────

# Bing News China RSS - reliably accessible
BING_CN_RSS_TEMPLATE = (
    "https://www.bing.com/news/search?q={query}&format=rss&cc=cn&mkt=zh-CN"
)

# Bing general search China
BING_CN_WEB_TEMPLATE = (
    "https://www.bing.com/search?q={query}&cc=cn&mkt=zh-CN"
)

# Google News China region
GOOGLE_NEWS_CN_TEMPLATE = (
    "https://news.google.com/rss/search?q={query}&hl=zh-CN&gl=CN&ceid=CN:zh-Hans"
)

# Sogou WeChat article search
SOGOU_WECHAT_TEMPLATE = (
    "https://weixin.sogou.com/weixin?type=2&query={query}"
)

# Zhihu search (returns HTML, needs parsing)
ZHIHU_SEARCH_TEMPLATE = (
    "https://www.zhihu.com/search?type=content&q={query}"
)

# Baidu news search (returns HTML)
BAIDU_NEWS_TEMPLATE = (
    "https://www.baidu.com/s?wd={query}&tn=news&rtt=1"
)


class ActiveSearchService:
    """Search external information sources through configured providers."""

    def __init__(self, config=Config):
        self.config = config

    def active_search(self, keyword: str) -> List[Dict[str, str]]:
        """Return raw documents for a keyword through configured providers."""
        keyword = (keyword or "").strip()
        if not keyword:
            raise ValueError("keyword is required")

        provider = (self.config.ACTIVE_SEARCH_PROVIDER or "chinese").strip().lower()
        max_results = max(1, int(self.config.ACTIVE_SEARCH_MAX_RESULTS))

        if provider == "rss":
            return self._rss_search(keyword, max_results)
        if provider in {"chinese", "cn", "all"}:
            return self._chinese_multi_search(keyword, max_results)
        if provider == "all":
            rss_docs = self._rss_search(keyword, max_results)
            cn_docs = self._chinese_multi_search(keyword, max_results)
            return self._dedup_by_url(rss_docs + cn_docs)[:max_results]

        raise ActiveSearchUnavailable(
            f"active search provider '{provider}' is not supported. "
            "Use 'rss', 'chinese', or 'all'."
        )

    # ── Chinese multi-source search ───────────────────────────

    def _chinese_multi_search(self, keyword: str, max_results: int) -> List[Dict[str, str]]:
        """Search across multiple Chinese web sources and aggregate results."""
        all_docs: List[Dict[str, str]] = []
        errors: List[str] = []

        # 1. Bing News China RSS (most reliable)
        try:
            docs = self._search_rss_source(
                BING_CN_RSS_TEMPLATE, keyword, "bing_cn"
            )
            all_docs.extend(docs)
        except Exception as exc:
            errors.append(f"bing_cn: {exc}")

        # 2. Google News China RSS
        try:
            docs = self._search_rss_source(
                GOOGLE_NEWS_CN_TEMPLATE, keyword, "google_news_cn"
            )
            all_docs.extend(docs)
        except Exception as exc:
            errors.append(f"google_news_cn: {exc}")

        # 3. Custom RSS URLs from config (if any)
        custom_urls = self._custom_rss_templates()
        for i, template in enumerate(custom_urls):
            try:
                docs = self._search_rss_source(template, keyword, f"custom_{i}")
                all_docs.extend(docs)
            except Exception as exc:
                errors.append(f"custom_rss_{i}: {exc}")

        all_docs = self._dedup_by_url(all_docs)[:max_results]

        # 4. Fallback: web search page parsing for extra sources
        if len(all_docs) < max_results:
            try:
                web_docs = self._web_search_fallback(
                    keyword, max_results - len(all_docs)
                )
                all_docs.extend(web_docs)
                all_docs = self._dedup_by_url(all_docs)[:max_results]
            except Exception as exc:
                errors.append(f"web_search: {exc}")

        if not all_docs:
            detail = "; ".join(errors) if errors else "no documents found"
            raise ActiveSearchUnavailable(
                f"chinese search returned no documents: {detail}"
            )

        return all_docs

    def _search_rss_source(
        self, template: str, keyword: str, label: str
    ) -> List[Dict[str, str]]:
        """Search a single RSS source."""
        url = template.format(query=quote_plus(keyword))
        timeout = max(3, int(self.config.ACTIVE_SEARCH_TIMEOUT_SECONDS))
        try:
            xml_bytes = self._fetch(url, timeout=timeout)
            return self._parse_rss(xml_bytes, feed_url=url)
        except Exception:
            return []

    def _web_search_fallback(
        self, keyword: str, max_results: int
    ) -> List[Dict[str, str]]:
        """Search web pages as fallback when RSS sources yield few results."""
        docs: List[Dict[str, str]] = []
        sources_to_try = [
            (BING_CN_WEB_TEMPLATE, "bing_web"),
        ]

        for template, label in sources_to_try:
            if len(docs) >= max_results:
                break
            try:
                url = template.format(query=quote_plus(keyword))
                timeout = max(5, int(self.config.ACTIVE_SEARCH_TIMEOUT_SECONDS))
                html_bytes = self._fetch(url, timeout=timeout)
                parsed = self._parse_html_search_results(
                    html_bytes, source_label=label
                )
                docs.extend(parsed[: max_results - len(docs)])
            except Exception:
                continue

        return docs[:max_results]

    def _parse_html_search_results(
        self, html_bytes: bytes, source_label: str
    ) -> List[Dict[str, str]]:
        """Extract search result snippets from an HTML search page."""
        text = html_bytes.decode("utf-8", errors="replace")
        docs: List[Dict[str, str]] = []
        seen_titles: Set[str] = set()

        # Bing HTML parser: look for result items
        # Bing wraps results in <li class="b_algo"> or <div class="b_caption">
        result_pattern = re.compile(
            r'<h2[^>]*>.*?<a[^>]*href="([^"]+)"[^>]*>(.*?)</a>.*?</h2>',
            re.DOTALL | re.IGNORECASE,
        )
        snippet_pattern = re.compile(
            r'<p[^>]*class="[^"]*b_lineclamp[^"]*"[^>]*>(.*?)</p>'
            r'|<div[^>]*class="[^"]*b_caption[^"]*"[^>]*>.*?<p[^>]*>(.*?)</p>',
            re.DOTALL | re.IGNORECASE,
        )

        for match in result_pattern.finditer(text):
            url = html.unescape(match.group(1) or "")
            title = self._strip_html(html.unescape(match.group(2) or ""))
            if not title or title in seen_titles:
                continue
            seen_titles.add(title)
            source = self._source_from_url(url)

            docs.append({
                "title": title[:200],
                "url": url,
                "source": source,
                "publish_time": "",
                "raw_text": f"{title}\n{source}",
            })

        return docs

    # ── RSS search (original) ──────────────────────────────────

    def _rss_search(self, keyword: str, max_results: int) -> List[Dict[str, str]]:
        """Search configured RSS feeds and normalize entries."""
        templates = self._rss_templates()
        timeout = max(3, int(self.config.ACTIVE_SEARCH_TIMEOUT_SECONDS))
        errors: List[str] = []
        docs: List[Dict[str, str]] = []

        for template in templates:
            url = self._format_rss_url(template, keyword)
            try:
                xml_bytes = self._fetch(url, timeout=timeout)
                docs.extend(self._parse_rss(xml_bytes, feed_url=url))
            except (HTTPError, URLError, ET.ParseError, TimeoutError, OSError) as exc:
                errors.append(f"{url}: {exc}")
                continue

            docs = self._dedup_by_url(docs)
            if len(docs) >= max_results:
                break

        docs = self._dedup_by_url(docs)[:max_results]
        if not docs:
            detail = "; ".join(errors) if errors else "rss feeds returned no items"
            raise ActiveSearchUnavailable(
                f"active search returned no documents: {detail}"
            )
        return docs

    def _rss_templates(self) -> List[str]:
        """Read comma-separated RSS URL templates from configuration."""
        raw = self.config.ACTIVE_SEARCH_RSS_URLS or ""
        templates = [item.strip() for item in raw.split(",") if item.strip()]
        if not templates:
            raise ActiveSearchUnavailable("ACTIVE_SEARCH_RSS_URLS is empty")
        return templates

    def _custom_rss_templates(self) -> List[str]:
        """Read additional Chinese RSS feeds from config (optional)."""
        raw = getattr(self.config, "ACTIVE_SEARCH_CN_RSS_URLS", "") or ""
        return [item.strip() for item in raw.split(",") if item.strip()]

    @staticmethod
    def _format_rss_url(template: str, keyword: str) -> str:
        """Fill an RSS template with an encoded query string."""
        encoded = quote_plus(keyword)
        if "{query}" in template or "{keyword}" in template:
            return template.format(query=encoded, keyword=encoded)
        separator = "&" if "?" in template else "?"
        return f"{template}{separator}q={encoded}"

    def _fetch(self, url: str, *, timeout: int) -> bytes:
        """Download a document with appropriate headers."""
        request = Request(
            url,
            headers={
                "User-Agent": self.config.ACTIVE_SEARCH_USER_AGENT,
                "Accept": (
                    "application/rss+xml, application/xml, text/html;"
                    "q=0.9, */*;q=0.8"
                ),
                "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.5",
            },
        )
        with urlopen(request, timeout=timeout) as response:
            return response.read()

    # ── RSS parsing ────────────────────────────────────────────

    def _parse_rss(
        self, xml_bytes: bytes, *, feed_url: str
    ) -> List[Dict[str, str]]:
        """Parse RSS items into the standard document shape."""
        root = ET.fromstring(xml_bytes)
        docs: List[Dict[str, str]] = []
        for item in self._iter_rss_items(root):
            title = self._child_text(item, "title")
            link = self._child_text(item, "link")
            description = self._clean_snippet(
                self._child_text(item, "description")
            )
            source = self._child_text(item, "source") or self._source_from_url(
                link or feed_url
            )
            publish_time = self._normalize_pubdate(
                self._child_text(item, "pubDate")
            )
            raw_text = "\n".join(
                part for part in [title, source, description] if part
            ).strip()
            if not title and not raw_text:
                continue
            docs.append({
                "title": title or raw_text[:120],
                "url": link or feed_url,
                "source": source,
                "publish_time": publish_time,
                "raw_text": raw_text,
            })
        return docs

    @staticmethod
    def _iter_rss_items(root: ET.Element) -> Iterable[ET.Element]:
        for element in root.iter():
            if ActiveSearchService._local_name(element.tag) == "item":
                yield element

    @staticmethod
    def _child_text(element: ET.Element, name: str) -> str:
        for child in list(element):
            if ActiveSearchService._local_name(child.tag) == name:
                return (child.text or "").strip()
        return ""

    @staticmethod
    def _local_name(tag: str) -> str:
        return tag.rsplit("}", 1)[-1] if "}" in tag else tag

    # ── Utility methods ────────────────────────────────────────

    @staticmethod
    def _clean_snippet(value: str) -> str:
        text = html.unescape(value or "")
        text = re.sub(r"<[^>]+>", " ", text)
        text = re.sub(r"\s+", " ", text)
        return text.strip()

    @staticmethod
    def _strip_html(value: str) -> str:
        """Fully strip HTML tags from a string."""
        text = html.unescape(value or "")
        text = re.sub(r"<[^>]+>", " ", text)
        text = re.sub(r"\s+", " ", text)
        return text.strip()

    @staticmethod
    def _normalize_pubdate(value: str) -> str:
        if not value:
            return ""
        try:
            parsed = parsedate_to_datetime(value)
            return parsed.isoformat()
        except (TypeError, ValueError, IndexError, OverflowError):
            return value

    @staticmethod
    def _source_from_url(value: str) -> str:
        host = urlparse(value or "").netloc
        return host.replace("www.", "") if host else "rss"

    @staticmethod
    def _dedup_by_url(docs: List[Dict[str, str]]) -> List[Dict[str, str]]:
        seen: Set[str] = set()
        unique: List[Dict[str, str]] = []
        for doc in docs:
            key = doc.get("url") or doc.get("title") or doc.get("raw_text")
            if not key or key in seen:
                continue
            seen.add(key)
            unique.append(doc)
        return unique


def active_search(keyword: str) -> List[Dict[str, str]]:
    """Convenience function used by Celery tasks and report tools."""
    return ActiveSearchService().active_search(keyword)
