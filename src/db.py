"""PostgreSQL connection helpers with retry/backoff."""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager

import psycopg2
from psycopg2.extensions import connection as PgConnection
from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from src.config import Settings, get_settings

_engine: Engine | None = None
_SessionLocal: sessionmaker[Session] | None = None


@retry(
    reraise=True,
    stop=stop_after_attempt(5),
    wait=wait_exponential(multiplier=0.4, min=0.4, max=8),
    retry=retry_if_exception_type(psycopg2.OperationalError),
)
def connect(settings: Settings | None = None) -> PgConnection:
    cfg = settings or get_settings()
    conn = psycopg2.connect(**cfg.psycopg2_kwargs)
    conn.autocommit = False
    return conn


@contextmanager
def connection(settings: Settings | None = None) -> Iterator[PgConnection]:
    conn = connect(settings)
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def get_engine(settings: Settings | None = None) -> Engine:
    global _engine
    cfg = settings or get_settings()
    if _engine is None:
        _engine = create_engine(cfg.database_url, pool_pre_ping=True, future=True)
    return _engine


def get_session_factory(settings: Settings | None = None) -> sessionmaker[Session]:
    global _SessionLocal
    if _SessionLocal is None:
        _SessionLocal = sessionmaker(
            autocommit=False,
            autoflush=False,
            bind=get_engine(settings),
            future=True,
        )
    return _SessionLocal
