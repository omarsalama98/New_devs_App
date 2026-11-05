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


SUNSET_PROPERTIES = [
    {"id": "prop-001", "name": "Beach House Alpha"},
    {"id": "prop-002", "name": "City Apartment Downtown"},
    {"id": "prop-003", "name": "Country Villa Estate"},
]
OCEAN_PROPERTIES = [
    {"id": "prop-004", "name": "Lakeside Cottage"},
    {"id": "prop-001", "name": "Mountain Lodge Beta"},
    {"id": "prop-005", "name": "Urban Loft Modern"},
]


def totals(response):
    assert response.status_code == 200, response.text
    body = response.json()
    return body["total_revenue"], body["reservations_count"]


# get_summary clears the cache once at setup, so the second call can hit what the first one stored
def test_prop_001_stays_separate_when_sunset_asks_first(get_summary, sunset_headers, ocean_headers):
    assert totals(get_summary(sunset_headers, "prop-001")) == (2250.0, 4)
    assert totals(get_summary(ocean_headers, "prop-001")) == (0.0, 0)


def test_prop_001_stays_separate_when_ocean_asks_first(get_summary, sunset_headers, ocean_headers):
    assert totals(get_summary(ocean_headers, "prop-001")) == (0.0, 0)
    assert totals(get_summary(sunset_headers, "prop-001")) == (2250.0, 4)


def test_cache_key_includes_the_tenant(get_summary, ocean_headers, live_redis):
    get_summary(ocean_headers, "prop-001")

    assert live_redis.exists("revenue:tenant-b:prop-001")


def test_each_client_lists_only_its_own_properties(get_properties, sunset_headers, ocean_headers):
    sunset = get_properties(sunset_headers)
    ocean = get_properties(ocean_headers)

    assert sunset.status_code == 200, sunset.text
    assert ocean.status_code == 200, ocean.text
    assert sunset.json() == {"items": SUNSET_PROPERTIES, "total": 3}
    assert ocean.json() == {"items": OCEAN_PROPERTIES, "total": 3}


def test_other_tenant_and_unknown_property_get_the_same_404(get_summary, ocean_headers, live_redis):
    other_tenant = get_summary(ocean_headers, "prop-002")
    unknown = get_summary(ocean_headers, "prop-999")

    assert other_tenant.status_code == 404
    assert unknown.status_code == 404
    assert other_tenant.json() == unknown.json()
    # A 404 is never cached
    assert live_redis.exists("revenue:tenant-b:prop-002", "revenue:tenant-b:prop-999") == 0


def test_simulated_tenant_header_is_ignored(get_summary, get_properties, ocean_headers):
    spoofed = {**ocean_headers, "X-Simulated-Tenant": "tenant-a"}

    assert totals(get_summary(spoofed, "prop-001")) == (0.0, 0)
    assert get_summary(spoofed, "prop-002").status_code == 404
    assert get_properties(spoofed).json()["items"] == OCEAN_PROPERTIES


def test_unknown_user_gets_403(get_summary, get_properties, unknown_user_headers):
    assert get_summary(unknown_user_headers, "prop-001").status_code == 403
    assert get_properties(unknown_user_headers).status_code == 403


def test_no_token_gets_401(get_summary, get_properties):
    assert get_summary(None, "prop-001").status_code == 401
    assert get_properties(None).status_code == 401


def test_properties_returns_503_with_no_figures_when_data_is_unavailable(offline_client):
    outage = reservations.RevenueDataUnavailable("database down")

    with patch("app.api.v1.dashboard.list_properties", side_effect=outage):
        response = offline_client.get("/api/v1/properties")

    assert response.status_code == 503
    assert list(response.json()) == ["detail"]


def test_prop_001_counts_march_and_february_in_paris_time(get_summary, sunset_headers):
    # res-tz-1 checks in at 23:30 UTC on 29 February, which is already 1 March in Paris
    assert totals(get_summary(sunset_headers, "prop-001", month=3, year=2024)) == (2250.0, 4)
    assert totals(get_summary(sunset_headers, "prop-001", month=2, year=2024)) == (0.0, 0)


def test_sunset_march_total_across_properties(get_summary, sunset_headers):
    revenue = [
        totals(get_summary(sunset_headers, prop["id"], month=3, year=2024))[0]
        for prop in SUNSET_PROPERTIES
    ]

    assert sum(revenue) == 13326.0


def test_late_march_check_in_counts_as_march_in_new_york(get_summary, ocean_headers, add_reservation):
    # 03:00 UTC on 1 April is 23:00 on 31 March in New York
    add_reservation("test-tz-new-york", "prop-004", "tenant-b", "2024-04-01 03:00:00+00", 100)

    assert totals(get_summary(ocean_headers, "prop-004", month=3, year=2024)) == (1876.5, 5)
    assert totals(get_summary(ocean_headers, "prop-004", month=4, year=2024)) == (0.0, 0)


def test_other_tenant_property_gets_404_for_a_month(get_summary, ocean_headers):
    assert get_summary(ocean_headers, "prop-002", month=3, year=2024).status_code == 404


def test_invalid_month_gets_422(get_summary, sunset_headers):
    assert get_summary(sunset_headers, "prop-001", month=13, year=2024).status_code == 422


@pytest.mark.parametrize("params", [{"month": 3}, {"year": 2024}])
def test_month_and_year_must_be_sent_together(get_summary, sunset_headers, params):
    assert get_summary(sunset_headers, "prop-001", **params).status_code == 400


def test_month_and_all_time_cache_entries_stay_separate(get_summary, sunset_headers, add_reservation, live_redis):
    # A May booking, so the all-time and March figures differ
    add_reservation("test-cache-may", "prop-001", "tenant-a", "2024-05-10 12:00:00+00", 100)

    # The second round reads what the first one stored
    for _ in range(2):
        assert totals(get_summary(sunset_headers, "prop-001")) == (2350.0, 5)
        assert totals(get_summary(sunset_headers, "prop-001", month=3, year=2024)) == (2250.0, 4)

    assert live_redis.exists("revenue:tenant-a:prop-001", "revenue:tenant-a:prop-001:2024-03") == 2
