"""Application configuration.

This module only reads environment variables and prepares safe defaults.
Business code should import values from ``Config`` instead of reading secrets
directly, so later infrastructure can be added without changing the old flow.
"""

import os
from urllib.parse import quote, quote_plus

from dotenv import load_dotenv


project_root_env = os.path.join(os.path.dirname(__file__), "../../.env")

if os.path.exists(project_root_env):
    load_dotenv(project_root_env, override=True)
else:
    load_dotenv(override=True)


def _env_bool(name: str, default: bool = False) -> bool:
    """Read a boolean environment variable with a safe fallback value."""
    value = os.environ.get(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _env_int(name: str, default: int) -> int:
    """Read an integer environment variable and keep startup stable if invalid."""
    value = os.environ.get(name)
    if value is None:
        return default
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _env_float(name: str, default: float) -> float:
    """Read a float environment variable and keep startup stable if invalid."""
    value = os.environ.get(name)
    if value is None:
        return default
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _build_mysql_url() -> str:
    """Build the default SQLAlchemy URL from MYSQL_* environment variables."""
    user = quote_plus(os.environ.get("MYSQL_USER", "mirofish"))
    password = quote_plus(os.environ.get("MYSQL_PASSWORD", "mirofish_password"))
    host = os.environ.get("MYSQL_HOST", "localhost")
    port = os.environ.get("MYSQL_PORT", "3306")
    database = quote_plus(os.environ.get("MYSQL_DATABASE", "mirofish"))
    return f"mysql+pymysql://{user}:{password}@{host}:{port}/{database}"


def _build_rabbitmq_url() -> str:
    """Build the default Celery broker URL from RABBITMQ_* variables."""
    user = quote_plus(os.environ.get("RABBITMQ_USER", "mirofish"))
    password = quote_plus(os.environ.get("RABBITMQ_PASSWORD", "mirofish_password"))
    host = os.environ.get("RABBITMQ_HOST", "localhost")
    port = os.environ.get("RABBITMQ_PORT", "5672")
    vhost = os.environ.get("RABBITMQ_VHOST", "/")
    vhost_path = "/" if vhost == "/" else quote(vhost.lstrip("/"), safe="")
    return f"amqp://{user}:{password}@{host}:{port}/{vhost_path}"


class Config:
    """Central Flask configuration object."""

    # Flask settings
    SECRET_KEY = os.environ.get("SECRET_KEY", "mirofish-secret-key")
    DEBUG = os.environ.get("FLASK_DEBUG", "True").lower() == "true"
    JSON_AS_ASCII = False

    # OpenAI-compatible LLM settings. The original code still reads LLM_*,
    # while enhanced modules can read OPENAI_* without duplicating secrets.
    OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY") or os.environ.get("LLM_API_KEY")
    OPENAI_BASE_URL = os.environ.get("OPENAI_BASE_URL") or os.environ.get(
        "LLM_BASE_URL", "https://api.openai.com/v1"
    )
    OPENAI_MODEL = os.environ.get("OPENAI_MODEL") or os.environ.get(
        "LLM_MODEL_NAME", "gpt-4o-mini"
    )
    EMBEDDING_MODEL = os.environ.get("EMBEDDING_MODEL", "text-embedding-3-small")

    LLM_API_KEY = os.environ.get("LLM_API_KEY") or OPENAI_API_KEY
    LLM_BASE_URL = os.environ.get("LLM_BASE_URL") or OPENAI_BASE_URL
    LLM_MODEL_NAME = os.environ.get("LLM_MODEL_NAME") or OPENAI_MODEL
    LLM_TIMEOUT_SECONDS = _env_float("LLM_TIMEOUT_SECONDS", 180.0)
    LLM_MAX_RETRIES = _env_int("LLM_MAX_RETRIES", 0)
    ONTOLOGY_LLM_TIMEOUT_SECONDS = _env_float("ONTOLOGY_LLM_TIMEOUT_SECONDS", 20.0)
    ONTOLOGY_LLM_MAX_TOKENS = _env_int("ONTOLOGY_LLM_MAX_TOKENS", 1600)
    ONTOLOGY_USE_FAST_PROMPT = _env_bool("ONTOLOGY_USE_FAST_PROMPT", True)
    ONTOLOGY_ENABLE_RULE_FALLBACK = _env_bool("ONTOLOGY_ENABLE_RULE_FALLBACK", True)
    ONTOLOGY_MAX_INPUT_CHARS = _env_int("ONTOLOGY_MAX_INPUT_CHARS", 6000)

    # Zep settings. ZEP_API_URL is reserved for future self-hosted or proxy use.
    ZEP_API_KEY = os.environ.get("ZEP_API_KEY")
    ZEP_API_URL = os.environ.get("ZEP_API_URL", "")
    ZEP_ENHANCED_GRAPH_ID = os.environ.get("ZEP_ENHANCED_GRAPH_ID", "mirofish_enhanced_memory")

    # MySQL settings reserved for long-term memory and Celery result backend.
    MYSQL_HOST = os.environ.get("MYSQL_HOST", "localhost")
    MYSQL_PORT = _env_int("MYSQL_PORT", 3306)
    MYSQL_USER = os.environ.get("MYSQL_USER", "mirofish")
    MYSQL_PASSWORD = os.environ.get("MYSQL_PASSWORD", "mirofish_password")
    MYSQL_DATABASE = os.environ.get("MYSQL_DATABASE", "mirofish")
    MYSQL_CONNECT_TIMEOUT = _env_int("MYSQL_CONNECT_TIMEOUT", 3)
    MYSQL_AUTO_CREATE_TABLES = _env_bool("MYSQL_AUTO_CREATE_TABLES", False)
    MYSQL_URL = os.environ.get("MYSQL_URL") or _build_mysql_url()
    SQLALCHEMY_DATABASE_URI = os.environ.get("SQLALCHEMY_DATABASE_URI") or MYSQL_URL
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # RabbitMQ and Celery settings reserved for async ingestion.
    RABBITMQ_HOST = os.environ.get("RABBITMQ_HOST", "localhost")
    RABBITMQ_PORT = _env_int("RABBITMQ_PORT", 5672)
    RABBITMQ_USER = os.environ.get("RABBITMQ_USER", "mirofish")
    RABBITMQ_PASSWORD = os.environ.get("RABBITMQ_PASSWORD", "mirofish_password")
    RABBITMQ_VHOST = os.environ.get("RABBITMQ_VHOST", "/")
    CELERY_BROKER_URL = os.environ.get("CELERY_BROKER_URL") or _build_rabbitmq_url()
    CELERY_RESULT_BACKEND = os.environ.get("CELERY_RESULT_BACKEND", "disabled://")
    CELERY_TASK_ALWAYS_EAGER = _env_bool("CELERY_TASK_ALWAYS_EAGER", False)
    CELERY_TASK_TIME_LIMIT = _env_int("CELERY_TASK_TIME_LIMIT", 600)
    CELERY_BROKER_CONNECTION_TIMEOUT = _env_int("CELERY_BROKER_CONNECTION_TIMEOUT", 3)

    # Chroma settings reserved for semantic memory.
    CHROMA_HOST = os.environ.get("CHROMA_HOST", "localhost")
    CHROMA_PORT = _env_int("CHROMA_PORT", 8000)
    CHROMA_PERSIST_DIR = os.environ.get(
        "CHROMA_PERSIST_DIR",
        os.path.join(os.path.dirname(__file__), "../uploads/chroma"),
    )
    CHROMA_HTTP_URL = os.environ.get("CHROMA_HTTP_URL", f"http://{CHROMA_HOST}:{CHROMA_PORT}")
    CHROMA_USE_HTTP = _env_bool("CHROMA_USE_HTTP", False)
    CHROMA_COLLECTION_NAME = os.environ.get("CHROMA_COLLECTION_NAME", "mirofish_memory")

    # Memory recall scoring settings.
    MEMORY_RECALL_SEMANTIC_WEIGHT = float(os.environ.get("MEMORY_RECALL_SEMANTIC_WEIGHT", "0.5"))
    MEMORY_RECALL_IMPORTANCE_WEIGHT = float(os.environ.get("MEMORY_RECALL_IMPORTANCE_WEIGHT", "0.3"))
    MEMORY_RECALL_TIME_DECAY_WEIGHT = float(os.environ.get("MEMORY_RECALL_TIME_DECAY_WEIGHT", "0.2"))
    MEMORY_RECALL_CANDIDATES = _env_int("MEMORY_RECALL_CANDIDATES", 20)
    MEMORY_TIME_DECAY_HALF_LIFE_DAYS = float(
        os.environ.get("MEMORY_TIME_DECAY_HALF_LIFE_DAYS", "30")
    )

    # Ingestion settings. Default to "chinese" provider for Chinese web sources
    # (Bing CN, Google News CN, custom RSS). Use "rss" for original RSS-only mode.
    ACTIVE_SEARCH_PROVIDER = os.environ.get("ACTIVE_SEARCH_PROVIDER", "chinese")
    ACTIVE_SEARCH_MAX_RESULTS = _env_int("ACTIVE_SEARCH_MAX_RESULTS", 5)
    ACTIVE_SEARCH_TIMEOUT_SECONDS = _env_int("ACTIVE_SEARCH_TIMEOUT_SECONDS", 20)
    ACTIVE_SEARCH_USER_AGENT = os.environ.get(
        "ACTIVE_SEARCH_USER_AGENT",
        "MiroFish-Pro/1.0 (+https://github.com/)",
    )
    ACTIVE_SEARCH_RSS_URLS = os.environ.get(
        "ACTIVE_SEARCH_RSS_URLS",
        "https://news.google.com/rss/search?q={query}&hl=zh-CN&gl=CN&ceid=CN:zh-Hans",
    )
    # Additional Chinese RSS feeds (comma-separated). Leave empty to use built-in
    # Bing CN + Google News CN sources only.
    ACTIVE_SEARCH_CN_RSS_URLS = os.environ.get("ACTIVE_SEARCH_CN_RSS_URLS", "")
    # Fallback static keywords (used only when dynamic extraction is disabled).
    INGESTION_KEYWORDS = os.environ.get("INGESTION_KEYWORDS", "")
    # When true, keywords are extracted dynamically from seed materials.
    # When false, static INGESTION_KEYWORDS are used.
    INGESTION_KEYWORDS_DYNAMIC = _env_bool("INGESTION_KEYWORDS_DYNAMIC", True)
    # Default interval for dynamic project-specific ingestion (seconds).
    INGESTION_INTERVAL_SECONDS = _env_int("INGESTION_INTERVAL_SECONDS", 1800)
    INGESTION_CONTENT_MIN_LENGTH = _env_int("INGESTION_CONTENT_MIN_LENGTH", 20)
    INGESTION_DEDUP_SIMILARITY_THRESHOLD = float(
        os.environ.get("INGESTION_DEDUP_SIMILARITY_THRESHOLD", "0.88")
    )
    SUMMARY_MAX_INPUT_CHARS = _env_int("SUMMARY_MAX_INPUT_CHARS", 4000)

    # Multi-agent review settings.
    REVIEW_CLAIM_MIN_LENGTH = _env_int("REVIEW_CLAIM_MIN_LENGTH", 12)
    REVIEW_MAX_CLAIMS = _env_int("REVIEW_MAX_CLAIMS", 20)
    REVIEW_EVIDENCE_TOP_K = _env_int("REVIEW_EVIDENCE_TOP_K", 5)
    REVIEW_USE_ACTIVE_SEARCH = _env_bool("REVIEW_USE_ACTIVE_SEARCH", False)

    # Upload settings
    MAX_CONTENT_LENGTH = 50 * 1024 * 1024
    UPLOAD_FOLDER = os.path.join(os.path.dirname(__file__), "../uploads")
    ALLOWED_EXTENSIONS = {"pdf", "md", "txt", "markdown"}

    # Text processing settings
    DEFAULT_CHUNK_SIZE = 500
    DEFAULT_CHUNK_OVERLAP = 50

    # OASIS simulation settings
    OASIS_DEFAULT_MAX_ROUNDS = _env_int("OASIS_DEFAULT_MAX_ROUNDS", 10)
    OASIS_SIMULATION_DATA_DIR = os.path.join(os.path.dirname(__file__), "../uploads/simulations")
    OASIS_TWITTER_ACTIONS = [
        "CREATE_POST",
        "LIKE_POST",
        "REPOST",
        "FOLLOW",
        "DO_NOTHING",
        "QUOTE_POST",
    ]
    OASIS_REDDIT_ACTIONS = [
        "LIKE_POST",
        "DISLIKE_POST",
        "CREATE_POST",
        "CREATE_COMMENT",
        "LIKE_COMMENT",
        "DISLIKE_COMMENT",
        "SEARCH_POSTS",
        "SEARCH_USER",
        "TREND",
        "REFRESH",
        "DO_NOTHING",
        "FOLLOW",
        "MUTE",
    ]

    # ReportAgent settings
    REPORT_AGENT_MAX_TOOL_CALLS = _env_int("REPORT_AGENT_MAX_TOOL_CALLS", 5)
    REPORT_AGENT_MAX_REFLECTION_ROUNDS = _env_int("REPORT_AGENT_MAX_REFLECTION_ROUNDS", 2)
    REPORT_AGENT_TEMPERATURE = float(os.environ.get("REPORT_AGENT_TEMPERATURE", "0.5"))

    # Traceable ReportAgent settings.
    TRACEABLE_REPORT_MEMORY_TOP_K = _env_int("TRACEABLE_REPORT_MEMORY_TOP_K", 5)
    TRACEABLE_REPORT_GRAPH_LIMIT = _env_int("TRACEABLE_REPORT_GRAPH_LIMIT", 5)
    TRACEABLE_REPORT_MAX_SEARCH_RESULTS = _env_int("TRACEABLE_REPORT_MAX_SEARCH_RESULTS", 5)
    TRACEABLE_REPORT_MAX_INTERVIEWS = _env_int("TRACEABLE_REPORT_MAX_INTERVIEWS", 5)
    TRACEABLE_REPORT_INTERVIEW_TIMEOUT_SECONDS = _env_float(
        "TRACEABLE_REPORT_INTERVIEW_TIMEOUT_SECONDS", 15.0
    )
    TRACEABLE_REPORT_REVIEW_MAX_CLAIMS = _env_int("TRACEABLE_REPORT_REVIEW_MAX_CLAIMS", 2)
    TRACEABLE_REPORT_FAST_REVIEW = _env_bool("TRACEABLE_REPORT_FAST_REVIEW", True)
    TRACEABLE_REPORT_MAX_TOKENS = _env_int("TRACEABLE_REPORT_MAX_TOKENS", 1200)
    TRACEABLE_REPORT_REVISE_WITH_LLM = _env_bool("TRACEABLE_REPORT_REVISE_WITH_LLM", False)
    TRACEABLE_REPORT_DRAFT_TIMEOUT_SECONDS = _env_float("TRACEABLE_REPORT_DRAFT_TIMEOUT_SECONDS", 30.0)

    @classmethod
    def validate(cls):
        """Validate only the credentials required by the original main flow."""
        errors = []
        placeholders = {
            "",
            "your_api_key_here",
            "your_openai_api_key_here",
            "your_chat_model_key_here",
            "your_zep_api_key_here",
        }
        if (cls.LLM_API_KEY or "").strip().lower() in placeholders:
            errors.append("LLM_API_KEY or OPENAI_API_KEY must be a real key")
        if (cls.ZEP_API_KEY or "").strip().lower() in placeholders:
            errors.append("ZEP_API_KEY must be a real key")
        return errors
