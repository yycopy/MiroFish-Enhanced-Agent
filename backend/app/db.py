"""Database bootstrap helpers for the enhanced MySQL memory layer.

The original MiroFish flow stores most runtime data in files. This module adds
an optional SQLAlchemy connection for new long-term memory features without
making MySQL a hard dependency of the old graph, simulation, or report APIs.
"""

from contextlib import contextmanager
from typing import Any, Dict, Optional

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine, make_url
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import DeclarativeBase, scoped_session, sessionmaker

from .config import Config
from .utils.logger import get_logger


logger = get_logger("mirofish.db")


class Base(DeclarativeBase):
    """Base class for all SQLAlchemy ORM models in the enhanced modules."""


class DatabaseUnavailableError(RuntimeError):
    """Raised when MySQL is not configured or cannot be reached."""


_engine: Optional[Engine] = None
_SessionLocal: Optional[scoped_session] = None
_last_error: Optional[str] = None


def _config_get(config: Any, name: str, default: Any = None) -> Any:
    """Read a config value from a Flask config dict or a Config-like object."""
    if isinstance(config, dict):
        return config.get(name, default)
    return getattr(config, name, default)


def _mask_database_url(database_url: str) -> str:
    """Mask the password before exposing a database url in logs or APIs."""
    try:
        return make_url(database_url).render_as_string(hide_password=True)
    except Exception:
        return "<invalid database url>"


def configure_database(
    config: Any = Config,
    *,
    test_connection: bool = False,
    create_tables: bool = False,
) -> Optional[Engine]:
    """Create the SQLAlchemy engine and session factory if possible.

    ``create_engine`` itself does not open a network connection, so calling this
    during Flask startup is low risk. Optional connection testing and table
    creation are wrapped so a missing MySQL server never crashes the old app.
    """
    global _engine, _SessionLocal, _last_error

    if _engine is not None and _SessionLocal is not None:
        return _engine

    database_url = _config_get(config, "SQLALCHEMY_DATABASE_URI") or _config_get(
        config, "MYSQL_URL"
    )
    if not database_url:
        _last_error = "mysql database url is not configured"
        logger.warning(_last_error)
        return None

    connect_args: Dict[str, Any] = {}
    if str(database_url).startswith("mysql"):
        connect_args = {
            "charset": "utf8mb4",
            "connect_timeout": int(_config_get(config, "MYSQL_CONNECT_TIMEOUT", 3)),
        }

    try:
        _engine = create_engine(
            database_url,
            pool_pre_ping=True,
            pool_recycle=3600,
            future=True,
            connect_args=connect_args,
        )
        _SessionLocal = scoped_session(
            sessionmaker(
                bind=_engine,
                autoflush=False,
                autocommit=False,
                expire_on_commit=False,
                future=True,
            )
        )

        if test_connection:
            with _engine.connect() as connection:
                connection.execute(text("select 1"))

        if create_tables:
            create_all_tables()

        _last_error = None
        return _engine
    except Exception as exc:
        _last_error = str(exc)
        logger.warning("mysql memory database is unavailable: %s", exc)
        return None


def init_app(app) -> None:
    """Initialize the optional MySQL layer for a Flask app.

    The app only builds the SQLAlchemy engine during startup. If
    ``MYSQL_AUTO_CREATE_TABLES`` is enabled, it also tries to create tables, but
    any failure is logged instead of raised so the original project still starts.
    """
    configure_database(app.config, test_connection=False, create_tables=False)

    if app.config.get("MYSQL_AUTO_CREATE_TABLES", False):
        try:
            create_all_tables()
        except DatabaseUnavailableError as exc:
            logger.warning("skip mysql table creation: %s", exc)

    @app.teardown_appcontext
    def remove_database_session(_exception=None):
        remove_session()


def create_all_tables() -> None:
    """Create enhanced MySQL tables for memory and ingestion modules."""
    engine = configure_database(Config)
    if engine is None:
        raise DatabaseUnavailableError(_last_error or "mysql database is unavailable")

    # Importing models here registers their table metadata on Base without
    # forcing SQLAlchemy into the original file-based models at app import time.
    from .models import ingestion as _ingestion_models  # noqa: F401
    from .models import memory as _memory_models  # noqa: F401
    from .models import review as _review_models  # noqa: F401

    try:
        Base.metadata.create_all(bind=engine)
    except SQLAlchemyError as exc:
        raise DatabaseUnavailableError(str(exc)) from exc


def get_session():
    """Return a SQLAlchemy session or raise a clear database error."""
    if _SessionLocal is None:
        configure_database(Config)
    if _SessionLocal is None:
        raise DatabaseUnavailableError(_last_error or "mysql database is unavailable")
    return _SessionLocal()


@contextmanager
def session_scope():
    """Provide a transactional session boundary for repository methods."""
    session = get_session()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def remove_session() -> None:
    """Remove the scoped session for the current Flask request context."""
    if _SessionLocal is not None:
        _SessionLocal.remove()


def dispose_database() -> None:
    """Dispose the engine. Useful for scripts and tests."""
    global _engine, _SessionLocal
    if _SessionLocal is not None:
        _SessionLocal.remove()
    if _engine is not None:
        _engine.dispose()
    _engine = None
    _SessionLocal = None


def database_health() -> Dict[str, Any]:
    """Return a connection health payload for the memory API."""
    database_url = Config.SQLALCHEMY_DATABASE_URI or Config.MYSQL_URL
    if not database_url:
        return {
            "configured": False,
            "connected": False,
            "database_url": None,
            "message": "mysql database url is not configured",
        }

    engine = configure_database(Config)
    if engine is None:
        return {
            "configured": True,
            "connected": False,
            "database_url": _mask_database_url(database_url),
            "message": _last_error or "mysql database is unavailable",
        }

    try:
        with engine.connect() as connection:
            connection.execute(text("select 1"))
        return {
            "configured": True,
            "connected": True,
            "database_url": _mask_database_url(database_url),
            "message": "mysql database is connected",
        }
    except Exception as exc:
        return {
            "configured": True,
            "connected": False,
            "database_url": _mask_database_url(database_url),
            "message": str(exc),
        }
