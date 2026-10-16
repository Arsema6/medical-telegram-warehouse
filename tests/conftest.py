from __future__ import annotations

import os
from collections.abc import Generator
from unittest.mock import MagicMock

import psycopg2
import pytest
from fastapi.testclient import TestClient

# Deterministic secrets for tests. Database settings are intentionally NOT
# forced here: tests must see the same configuration as the application
# (environment variables, then .env, then the Settings defaults) so that the
# integration tests exercise the database the operator actually configured.
os.environ.setdefault("API_KEY", "test-api-key")
os.environ.setdefault("SKIP_YOLO", "1")

from src.config import get_settings  # noqa: E402

get_settings.cache_clear()


def postgres_available() -> bool:
    settings = get_settings()
    try:
        conn = psycopg2.connect(**settings.psycopg2_kwargs, connect_timeout=2)
        conn.close()
        return True
    except psycopg2.Error:
        return False


@pytest.fixture
def api_key() -> str:
    return os.environ["API_KEY"]


@pytest.fixture
def client() -> Generator[TestClient, None, None]:
    from api.database import get_db
    from api.main import app

    mock_db = MagicMock()
    mock_result = MagicMock()
    mock_result.fetchall.return_value = []
    mock_result.fetchone.return_value = None
    mock_result.scalar.return_value = 0
    mock_db.execute.return_value = mock_result

    def override_db():
        yield mock_db

    app.dependency_overrides[get_db] = override_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


@pytest.fixture
def mock_session() -> MagicMock:
    session = MagicMock()
    result = MagicMock()
    result.fetchall.return_value = []
    result.fetchone.return_value = None
    result.scalar.return_value = 0
    session.execute.return_value = result
    return session
