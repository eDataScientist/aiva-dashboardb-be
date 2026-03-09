import pytest
from httpx import AsyncClient


class TestProtectedRouteAuth:
    @pytest.mark.asyncio
    async def test_analytics_summary_requires_auth(self, client: AsyncClient):
        response = await client.get(
            "/api/v1/analytics/summary?start_date=2025-01-01&end_date=2025-01-31"
        )
        assert response.status_code == 401
        data = response.json()
        assert "detail" in data
        detail = data["detail"]
        assert detail.get("code") == "authentication_required"

    @pytest.mark.asyncio
    async def test_analytics_summary_rejects_invalid_token(self, client: AsyncClient):
        response = await client.get(
            "/api/v1/analytics/summary?start_date=2025-01-01&end_date=2025-01-31",
            headers={"Authorization": "Bearer invalid_token"},
        )
        assert response.status_code == 401
        data = response.json()
        detail = data.get("detail", {})
        assert detail.get("code") == "invalid_token"

    @pytest.mark.asyncio
    async def test_analytics_summary_rejects_missing_bearer(self, client: AsyncClient):
        # HTTPBearer(auto_error=False) returns None for non-Bearer schemes,
        # so the dep raises authentication_required rather than invalid_token.
        response = await client.get(
            "/api/v1/analytics/summary?start_date=2025-01-01&end_date=2025-01-31",
            headers={"Authorization": "Basic dXNlcjpwYXNz"},
        )
        assert response.status_code == 401
        data = response.json()
        detail = data.get("detail", {})
        assert detail.get("code") == "authentication_required"

    @pytest.mark.asyncio
    async def test_conversations_list_requires_auth(self, client: AsyncClient):
        response = await client.get("/api/v1/conversations")
        assert response.status_code == 401
        data = response.json()
        detail = data.get("detail", {})
        assert detail.get("code") == "authentication_required"

    @pytest.mark.asyncio
    async def test_conversations_messages_requires_auth(self, client: AsyncClient):
        response = await client.get("/api/v1/conversations/abc123/messages")
        assert response.status_code == 401
        data = response.json()
        detail = data.get("detail", {})
        assert detail.get("code") == "authentication_required"


class TestPublicRoutes:
    @pytest.mark.asyncio
    async def test_health_is_public(self, client: AsyncClient):
        response = await client.get("/health")
        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_login_is_public(self, client: AsyncClient):
        response = await client.post(
            "/api/v1/auth/login",
            json={"email": "test@example.com", "password": "test"},
        )
        assert response.status_code in (401, 422)


class TestAuthEndpointBehavior:
    @pytest.mark.asyncio
    async def test_login_rejects_blank_email(self, client: AsyncClient):
        response = await client.post(
            "/api/v1/auth/login",
            json={"email": "", "password": "password"},
        )
        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_login_rejects_blank_password(self, client: AsyncClient):
        response = await client.post(
            "/api/v1/auth/login",
            json={"email": "test@example.com", "password": ""},
        )
        assert response.status_code == 422
