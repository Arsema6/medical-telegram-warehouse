from __future__ import annotations

from collections.abc import Generator
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

from api.database import get_db
from api.main import app
from api.schemas import TopProductsResponse, VisualContent


@pytest.fixture
def api_client() -> Generator[TestClient, None, None]:
    session = MagicMock()

    def execute(stmt, params=None):
        sql = str(stmt)
        result = MagicMock()
        if "SELECT 1" in sql:
            return result
        if "FROM dim_channels" in sql and "total_posts" in sql:
            result.fetchall.return_value = [("chemed", "Medical", 5, 243.0)]
            return result
        if "FROM dim_channels WHERE channel_name" in sql:
            if params and params.get("channel_name") == "missing":
                result.fetchone.return_value = None
            else:
                result.fetchone.return_value = ("chemed", "Medical")
            return result
        if "COUNT(*) FROM fct_messages" in sql:
            result.scalar.return_value = 5
            return result
        if "GROUP BY d.date_key" in sql:
            result.fetchall.return_value = [(20240601, 3)]
            return result
        if "f.message_text" in sql and "ILIKE" in sql:
            result.fetchall.return_value = [
                (101, "chemed", "Paracetamol 500mg tablets available", 320, 20240601)
            ]
            return result
        if "SELECT f.message_text" in sql:
            result.fetchall.return_value = [
                ("Paracetamol 500mg tablets available",),
                ("Amoxicillin capsules in stock",),
            ]
            return result
        if "has_image = true" in sql:
            result.fetchall.return_value = [("chemed", 2)]
            return result
        if "FROM fct_image_detections" in sql:
            result.fetchall.return_value = [("promotional", 2), ("product_display", 3)]
            return result
        result.fetchall.return_value = []
        result.fetchone.return_value = None
        result.scalar.return_value = 0
        return result

    session.execute.side_effect = execute

    def override_db():
        yield session

    app.dependency_overrides[get_db] = override_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


def test_health_is_public(api_client: TestClient) -> None:
    response = api_client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_api_requires_key(api_client: TestClient) -> None:
    response = api_client.get("/api/reports/top-products")
    assert response.status_code == 401


def test_top_products_validates_response(api_client: TestClient) -> None:
    response = api_client.get(
        "/api/reports/top-products?limit=5",
        headers={"X-API-Key": "test-api-key"},
    )
    assert response.status_code == 200
    parsed = TopProductsResponse.model_validate(response.json())
    assert parsed.items
    assert parsed.items[0].term == "paracetamol"


def test_search_uses_parameterized_query(api_client: TestClient) -> None:
    response = api_client.get(
        "/api/search/messages?query=paracetamol&limit=10&offset=0&sort=views&order=desc",
        headers={"X-API-Key": "test-api-key"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["returned"] == 1
    assert "Paracetamol" in body["items"][0]["message_text"]


def test_search_rejects_unknown_sort(api_client: TestClient) -> None:
    response = api_client.get(
        "/api/search/messages?query=para&sort=drop table",
        headers={"X-API-Key": "test-api-key"},
    )
    assert response.status_code == 422


def test_channel_activity_404(api_client: TestClient) -> None:
    response = api_client.get(
        "/api/channels/missing/activity",
        headers={"X-API-Key": "test-api-key"},
    )
    assert response.status_code == 404


def test_channel_activity_ok(api_client: TestClient) -> None:
    response = api_client.get(
        "/api/channels/chemed/activity",
        headers={"X-API-Key": "test-api-key"},
    )
    assert response.status_code == 200
    assert response.json()["total_posts"] == 5


def test_visual_content_schema(api_client: TestClient) -> None:
    response = api_client.get(
        "/api/reports/visual-content",
        headers={"X-API-Key": "test-api-key"},
    )
    assert response.status_code == 200
    parsed = VisualContent.model_validate(response.json())
    assert parsed.promotional_count == 2
    assert parsed.product_display_count == 3


def test_list_channels(api_client: TestClient) -> None:
    response = api_client.get("/api/channels", headers={"X-API-Key": "test-api-key"})
    assert response.status_code == 200
    assert response.json()["count"] == 1


def test_search_rejects_short_query(api_client: TestClient) -> None:
    response = api_client.get(
        "/api/search/messages?query=a",
        headers={"X-API-Key": "test-api-key"},
    )
    assert response.status_code == 422


def test_top_products_rejects_out_of_range_limit(api_client: TestClient) -> None:
    response = api_client.get(
        "/api/reports/top-products?limit=0",
        headers={"X-API-Key": "test-api-key"},
    )
    assert response.status_code == 422


def test_search_rejects_bad_order(api_client: TestClient) -> None:
    response = api_client.get(
        "/api/search/messages?query=para&order=sideways",
        headers={"X-API-Key": "test-api-key"},
    )
    assert response.status_code == 422


def test_channel_list_filters_by_type(api_client: TestClient) -> None:
    response = api_client.get(
        "/api/channels?channel_type=Medical",
        headers={"X-API-Key": "test-api-key"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["count"] == 1
    assert body["items"][0]["channel_type"] == "Medical"
