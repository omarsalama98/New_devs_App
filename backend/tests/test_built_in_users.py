import pytest
import requests
from jose import jwt

from conftest import API_URL

# The starter's mock auth client accepts these without a real login, as its built-in candidate user
HARDCODED_TOKEN = "mock-token-123"
TOKEN_WITH_WRONG_SECRET = jwt.encode(
    {"id": "x", "email": "candidate@propertyflow.com", "aud": "authenticated"},
    "not-the-secret",
    algorithm="HS256",
)


@pytest.mark.parametrize("token", [HARDCODED_TOKEN, TOKEN_WITH_WRONG_SECRET])
def test_built_in_user_tokens_get_no_client_data(get_summary, get_properties, token):
    headers = {"Authorization": f"Bearer {token}"}

    assert get_summary(headers, "prop-001").status_code == 403
    assert get_properties(headers).status_code == 403


def test_login_without_a_password_gets_no_client_data(get_summary, get_properties):
    login = requests.post(
        f"{API_URL}/api/v1/auth/login",
        json={"email": "candidate@propertyflow.com", "password": "anything"},
        timeout=10,
    )
    headers = {"Authorization": f"Bearer {login.json()['access_token']}"}

    assert get_summary(headers, "prop-001").status_code == 403
    assert get_properties(headers).status_code == 403
