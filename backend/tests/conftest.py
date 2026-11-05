import pytest
import redis
import requests
from jose import jwt

# Host ports published by docker-compose.yml
API_URL = "http://localhost:8000"
REDIS_URL = "redis://localhost:6380/0"
# SECRET_KEY in docker-compose.yml
SECRET_KEY = "debug_challenge_secret"

SUNSET = ("sunset@propertyflow.com", "client_a_2024")
OCEAN = ("ocean@propertyflow.com", "client_b_2024")


@pytest.fixture(scope="session")
def live_redis():
    """Stops the whole run with one clear message when the stack isn't up."""
    client = redis.Redis.from_url(REDIS_URL)
    try:
        requests.get(f"{API_URL}/docs", timeout=5).raise_for_status()
        client.ping()
    except (requests.RequestException, redis.RedisError) as error:
        pytest.exit(
            f"Live stack not reachable ({error}). Start it with: docker compose up --build -d",
            returncode=1,
        )
    return client


def login(email, password):
    response = requests.post(
        f"{API_URL}/api/v1/auth/login",
        json={"email": email, "password": password},
        timeout=10,
    )
    if response.status_code != 200:
        pytest.exit(f"Login failed for {email}: {response.status_code} {response.text}", returncode=1)
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


@pytest.fixture(scope="session")
def sunset_headers(live_redis):
    return login(*SUNSET)


@pytest.fixture(scope="session")
def ocean_headers(live_redis):
    return login(*OCEAN)


@pytest.fixture(scope="session")
def unknown_user_headers(live_redis):
    """A validly signed token for an email that has no tenant mapping."""
    token = jwt.encode(
        {"id": "unknown-user", "email": "nobody@example.com", "aud": "authenticated"},
        SECRET_KEY,
        algorithm="HS256",
    )
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def clear_revenue_cache(live_redis):
    """Removes only the revenue entries, so each live test starts from an empty cache."""
    for key in live_redis.scan_iter(match="revenue:*"):
        live_redis.delete(key)


@pytest.fixture
def get_summary(clear_revenue_cache):
    """Calls the dashboard summary on the running API, as the client whose headers are passed."""

    def call(headers, property_id, **params):
        return requests.get(
            f"{API_URL}/api/v1/dashboard/summary",
            params={"property_id": property_id, **params},
            headers=headers,
            timeout=10,
        )

    return call


@pytest.fixture
def get_properties(live_redis):
    """Calls the property list on the running API, as the client whose headers are passed."""

    def call(headers):
        return requests.get(f"{API_URL}/api/v1/properties", headers=headers, timeout=10)

    return call
