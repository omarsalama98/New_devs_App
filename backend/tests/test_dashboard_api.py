import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.exc import SQLAlchemyError

from app.core.auth import authenticate_request
from app.main import app
from app.services import reservations
from app.services.cache import get_revenue_summary


@pytest.mark.parametrize(
    "property_id, total, count",
    [
        ("prop-001", 2250.0, 4),
        ("prop-002", 4975.5, 4),
        ("prop-003", 6100.5, 2),
    ],
)
def test_sunset_gets_real_totals(get_summary, sunset_headers, property_id, total, count):
    response = get_summary(sunset_headers, property_id)

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["total_revenue"] == total
    assert body["reservations_count"] == count


@pytest.mark.parametrize(
    "property_id, total, count",
    [
        ("prop-001", 0.0, 0),  # Ocean's own prop-001 has no bookings
        ("prop-004", 1776.5, 4),
        ("prop-005", 3256.0, 3),
    ],
)
def test_ocean_gets_real_totals(get_summary, ocean_headers, property_id, total, count):
    response = get_summary(ocean_headers, property_id)

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["total_revenue"] == total
    assert body["reservations_count"] == count


@pytest.fixture
def offline_client():
    """Calls the app in-process. No `with` block, so lifespan doesn't run and no stack is needed."""
    app.dependency_overrides[authenticate_request] = lambda: SimpleNamespace(tenant_id="tenant-a")
    yield TestClient(app)
    app.dependency_overrides.clear()


def test_summary_returns_503_with_no_figures_when_data_is_unavailable(offline_client):
    outage = reservations.RevenueDataUnavailable("database down")

    with patch("app.api.v1.dashboard.get_revenue_summary", side_effect=outage):
        response = offline_client.get("/api/v1/dashboard/summary", params={"property_id": "prop-001"})

    assert response.status_code == 503
    assert list(response.json()) == ["detail"]


def test_failed_calculation_is_not_cached():
    outage = reservations.RevenueDataUnavailable("database down")

    with (
        patch("app.services.cache.redis_client", new_callable=AsyncMock) as fake_redis,
        patch("app.services.reservations.calculate_total_revenue", side_effect=outage),
    ):
        fake_redis.get.return_value = None
        with pytest.raises(reservations.RevenueDataUnavailable):
            asyncio.run(get_revenue_summary("prop-001", "tenant-a"))

    fake_redis.setex.assert_not_called()


# A closed port raises OSError and a bad password raises a SQLAlchemy error
@pytest.mark.parametrize("error", [OSError("connection refused"), SQLAlchemyError("bad password")])
def test_database_errors_become_unavailable(error):
    with patch("app.services.reservations.db_pool") as pool:
        pool.get_session.side_effect = error
        with pytest.raises(reservations.RevenueDataUnavailable):
            asyncio.run(reservations.calculate_total_revenue("prop-001", "tenant-a"))


def test_pool_that_failed_to_initialise_is_unavailable():
    # DatabasePool.initialize() swallows its own errors and leaves session_factory as None
    with patch("app.services.reservations.db_pool") as pool:
        pool.session_factory = None
        pool.initialize = AsyncMock()
        with pytest.raises(reservations.RevenueDataUnavailable):
            asyncio.run(reservations.calculate_total_revenue("prop-001", "tenant-a"))
