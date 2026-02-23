import pytest

@pytest.mark.asyncio
async def test_health_check(client):
    """Verify that the test database and application health route respond correctly."""
    response = await client.get("/health")
    # if there is no health route, test will fail, which is good.
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
