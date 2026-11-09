import asyncio
from unittest.mock import patch

import pytest
from starlette.requests import Request
from starlette.responses import Response

from app import auth


def request(path="/", token=None, method="GET"):
    headers = [] if token is None else [(b"cookie", f"{auth.COOKIE_NAME}={token}".encode())]
    return Request({
        "type": "http", "method": method, "path": path, "scheme": "http",
        "query_string": b"", "headers": headers, "server": ("localhost", 8000),
        "client": ("127.0.0.1", 12345),
    })


@pytest.fixture(autouse=True)
def clean_sessions():
    auth.sessions.clear()
    auth.login_attempts.clear()
    yield
    auth.sessions.clear()
    auth.login_attempts.clear()


def protected_response(path, token=None):
    async def next_response(incoming):
        return Response("protected content")
    return asyncio.run(auth.require_login(request(path, token), next_response))


@pytest.mark.parametrize("path", ["/", "/static/index.html", "/static/responses.html", "/docs", "/openapi.json"])
def test_pages_require_login(path):
    response = protected_response(path)
    assert response.status_code == 303
    assert response.headers["location"] == "/login"
    assert response.headers["cache-control"] == "no-store"


@pytest.mark.parametrize("path", ["/api/participants-table", "/api/participants-table/export", "/api/participants/1"])
def test_api_requires_login(path):
    assert protected_response(path).status_code == 401


@pytest.mark.parametrize("path", ["/login", "/static/css/style.css"])
def test_login_assets_are_public(path):
    assert protected_response(path).status_code == 200


def test_login_logout_and_cookie_replay():
    password_hash = auth.hash_password("test-password")
    with patch.object(auth.settings, "login_username", "research"), patch.object(
        auth.settings, "login_password_hash", password_hash
    ):
        failed = auth.login(request("/login"), "research", "wrong")
        assert failed.headers["location"] == "/login?error=invalid"
        assert not auth.sessions
        response = auth.login(request("/login"), "research", "test-password")

    assert response.headers["location"] == "/"
    cookie = response.headers["set-cookie"]
    assert "HttpOnly" in cookie
    assert "SameSite=strict" in cookie
    assert "Max-Age=28800" in cookie
    token = next(iter(auth.sessions))
    assert protected_response("/", token).status_code == 200
    assert protected_response("/", "forged-token").status_code == 303
    assert auth.logout(request("/logout", token, "POST")).status_code == 303
    assert protected_response("/", token).status_code == 303


def test_expired_session_is_rejected():
    auth.sessions["expired"] = 1
    assert protected_response("/api/participants-table", "expired").status_code == 401
    assert "expired" not in auth.sessions


def test_login_page_is_visible_with_an_active_session():
    auth.sessions["active"] = auth.time.time() + 60
    response = auth.login_page(request("/login", "active"))
    assert response.status_code == 200
    assert b'<title>Login | Hair Research Database</title>' in response.body


def test_failed_logins_are_limited():
    with patch.object(auth.settings, "login_username", "research"), patch.object(
        auth.settings, "login_password_hash", "salt$invalid"
    ), patch.object(auth, "password_matches", return_value=False):
        for _ in range(5):
            assert auth.login(request("/login"), "research", "wrong").headers["location"] == "/login?error=invalid"
        response = auth.login(request("/login"), "research", "wrong")
        assert response.headers["location"] == "/login?error=limited"


def test_missing_credentials_fail_closed():
    with patch.object(auth.settings, "login_password_hash", ""):
        assert auth.login(request("/login"), "research", "password").status_code == 503


def test_password_hash_is_salted_and_checks_password():
    hashed = auth.hash_password("correct")
    assert auth.password_matches("correct", hashed)
    assert not auth.password_matches("wrong", hashed)
    assert not auth.password_matches("correct", "")
    assert hashed != auth.hash_password("correct")
