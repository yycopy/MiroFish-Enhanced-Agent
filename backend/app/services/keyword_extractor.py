"""从用户上传的种子材料中动态提取搜索关键词."""

import json
from typing import Any, Dict, List, Optional

from ..config import Config
from ..utils.llm_client import LLMClient
from ..utils.logger import get_logger

logger = get_logger("mirofish.keyword_extractor")


class KeywordExtractor:
    """使用LLM从种子材料中提取核心主题关键词."""

    def __init__(self, config=Config):
        self.config = config

    def extract_keywords(
        self,
        text: str,
        simulation_requirement: str = "",
        max_keywords: int = 8,
    ) -> Dict[str, Any]:
        """从文本中提取用于主动搜索的关键词列表。

        Args:
            text: 用户上传的种子材料全文
            simulation_requirement: 用户设定的仿真需求
            max_keywords: 最多提取关键词数

        Returns:
            {"keywords": [...], "search_queries": [...], "domain_tags": [...]}
        """
        text = (text or "").strip()
        if not text:
            raise ValueError("种子材料文本为空")

        # 截取前6000字符给LLM（节约token）
        truncated = text[:self.config.ONTOLOGY_MAX_INPUT_CHARS]
        sim_req = (simulation_requirement or "")[:500]

        try:
            return self._llm_extract(truncated, sim_req, max_keywords)
        except Exception as exc:
            logger.warning("LLM关键词提取失败，使用规则回退: %s", exc)
            return self._fallback_extract(truncated, sim_req, max_keywords)

    def _llm_extract(
        self, text: str, sim_req: str, max_keywords: int
    ) -> Dict[str, Any]:
        """使用LLM提取结构化关键词."""
        client = LLMClient(timeout=30, max_retries=1)

        system_prompt = (
            "你是一个信息检索专家。从给定的文档中提取用于中文互联网搜索的关键词。"
            "输出严格JSON格式。"
        )
        user_prompt = (
            "请从以下文档中提取关键词，用于在知乎、百度等中文网站搜索相关信息。\n\n"
            f"仿真需求: {sim_req if sim_req else '未指定'}\n"
            f"文档内容:\n{text[:4000]}\n\n"
            "返回JSON格式:\n"
            "{\n"
            '  "keywords": ["关键词1", "关键词2", ...],  // 核心主题词，2-8个\n'
            '  "search_queries": ["搜索查询1", ...],      // 组合搜索短语，适合搜索引擎，3-6个\n'
            '  "domain_tags": ["领域标签1", ...]          // 领域分类标签，3-5个\n'
            "}\n\n"
            "要求:\n"
            "1. keywords 应该是简短的核心主题词（2-8个字）\n"
            "2. search_queries 应该是完整的搜索短语，适合在搜索引擎中直接使用\n"
            "3. domain_tags 应该是领域分类标签\n"
            "4. 所有词应该与文档内容紧密相关\n"
            "5. 主要面向中文信息源，用中文输出"
        )

        response = client.chat(
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.2,
            max_tokens=800,
        )

        result = self._parse_json_response(response)
        return self._normalize_result(result, max_keywords)

    def _fallback_extract(
        self, text: str, sim_req: str, max_keywords: int
    ) -> Dict[str, Any]:
        """规则回退：高频词提取."""
        import re

        # 简单的中文分词启发式方法
        # 提取2-6字的中文短语
        words = re.findall(r"[一-龥]{2,6}", text)
        word_freq: Dict[str, int] = {}
        stop_words = {
            "可以", "进行", "一个", "这个", "没有", "他们", "我们", "什么",
            "因为", "所以", "但是", "如果", "虽然", "而且", "或者", "以及",
            "已经", "正在", "将要", "可能", "应该", "需要", "通过", "根据",
            "关于", "对于", "由于", "所以", "因此", "然而", "不过",
            "一些", "所有", "这些", "那些", "每个", "任何", "很多",
            "第一", "第二", "第三", "首先", "其次", "最后",
        }
        for w in words:
            if w not in stop_words:
                word_freq[w] = word_freq.get(w, 0) + 1

        sorted_words = sorted(word_freq.items(), key=lambda x: x[1], reverse=True)
        keywords = [w for w, _ in sorted_words[:max_keywords]]
        search_queries = keywords[:6]

        # 从sim_req中提取
        if sim_req:
            keywords = list(dict.fromkeys(re.findall(r"[一-龥]{2,6}", sim_req) + keywords))
            keywords = keywords[:max_keywords]

        return {
            "keywords": keywords,
            "search_queries": search_queries,
            "domain_tags": keywords[:3] if keywords else [],
        }

    @staticmethod
    def _parse_json_response(response: str) -> Dict[str, Any]:
        """解析LLM返回的JSON."""
        import re

        cleaned = response.strip()
        cleaned = re.sub(r"^```(?:json)?\s*\n?", "", cleaned, flags=re.IGNORECASE)
        cleaned = re.sub(r"\n?```\s*$", "", cleaned)
        return json.loads(cleaned)

    @staticmethod
    def _normalize_result(
        result: Dict[str, Any], max_keywords: int
    ) -> Dict[str, Any]:
        """标准化提取结果."""
        def _list(value: Any) -> List[str]:
            if value is None:
                return []
            if isinstance(value, list):
                return [str(v).strip() for v in value if str(v).strip()]
            return [str(value).strip()]

        keywords = _list(result.get("keywords"))[:max_keywords]
        search_queries = _list(result.get("search_queries"))[:max(6, max_keywords)]
        domain_tags = _list(result.get("domain_tags"))[:5]

        # 如果search_queries为空，用keywords组合
        if not search_queries and keywords:
            search_queries = keywords[:6]

        return {
            "keywords": keywords,
            "search_queries": search_queries,
            "domain_tags": domain_tags,
        }


def extract_keywords(
    text: str,
    simulation_requirement: str = "",
    max_keywords: int = 8,
) -> Dict[str, Any]:
    """便捷函数."""
    return KeywordExtractor().extract_keywords(text, simulation_requirement, max_keywords)
