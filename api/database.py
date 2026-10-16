"""SQLAlchemy session factory for FastAPI."""

from __future__ import annotations

from collections.abc import Generator

from sqlalchemy.orm import Session

from src.db import get_session_factory


def get_db() -> Generator[Session, None, None]:
    factory = get_session_factory()
    db = factory()
    try:
        yield db
    finally:
        db.close()
