"""Database engine and session factory."""

from __future__ import annotations

from collections.abc import Generator

from sqlalchemy import create_engine, event, text
from sqlalchemy.orm import Session, sessionmaker

from app.config import get_settings

_engines: dict = {}
_sessionmakers: dict = {}


def _build_engine(url: str):
    connect_args = {}
    if url.startswith("sqlite"):
        connect_args["check_same_thread"] = False
    engine = create_engine(url, connect_args=connect_args, pool_pre_ping=True)
    if url.startswith("sqlite"):

        @event.listens_for(engine, "connect")
        def _sqlite_pragmas(connection, _record):  # noqa: ANN001
            cursor = connection.cursor()
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.close()

    return engine


def get_engine():
    url = get_settings().database_url
    if url not in _engines:
        _engines[url] = _build_engine(url)
        _sessionmakers[url] = sessionmaker(bind=_engines[url], autoflush=False, autocommit=False)
    return _engines[url]


def get_sessionmaker():
    get_engine()
    return _sessionmakers[get_settings().database_url]


def get_db() -> Generator[Session, None, None]:
    session = get_sessionmaker()()
    try:
        yield session
    finally:
        session.close()


def check_database() -> bool:
    try:
        with get_engine().connect() as connection:
            connection.execute(text("SELECT 1"))
        return True
    except Exception:
        return False


def reset_database_state() -> None:
    from app.config import reset_settings_cache

    reset_settings_cache()
    for engine in _engines.values():
        engine.dispose()
    _engines.clear()
    _sessionmakers.clear()
