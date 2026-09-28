import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from cryptography.fernet import Fernet

from app.config import Settings, get_settings
from app.main import lifespan

ORIGIN = {"Origin": "https://portal.example"}


def _settings(tmp_path, demo_mode=True, **overrides):
    return Settings(
        database_path=str(tmp_path / "provider.db"),
        provider_key_pepper="p" * 40,
        provider_secret_key=Fernet.generate_key().decode(),
        portal_demo_mode=demo_mode,
        portal_public_origin="https://portal.example",
        _env_file=None,
        **overrides,
    )


def _demo_client(settings):
    """Fresh app per test: lifespan adds routes bound to this test's service."""
    from contextlib import contextmanager

    from app.main import lifespan, security_headers_middleware

    @contextmanager
    def factory():
        local_app = FastAPI(lifespan=lifespan)
        local_app.middleware("http")(security_headers_middleware)
        local_app.dependency_overrides[get_settings] = lambda: settings
        with TestClient(local_app, base_url="https://portal.example") as client:
            yield client

    return factory()


def test_demo_mode_serves_session_without_any_cookie(tmp_path):
    with _demo_client(_settings(tmp_path)) as client:
        response = client.get("/api/session")

        assert response.status_code == 200
        body = response.json()
        assert body["role"] == "operator"
        assert body["user"]["displayName"]
        session_cookie = next(value for value in response.headers.get_list("set-cookie") if value.startswith("portal_session="))
        assert "partitioned" in session_cookie.lower() and "secure" in session_cookie.lower()


def test_demo_mode_survives_browsers_that_drop_cookies(tmp_path):
    with _demo_client(_settings(tmp_path)) as client:
        first = client.get("/api/session", headers=ORIGIN)
        assert first.status_code == 200
        csrf = first.json()["csrfToken"]

        # Simulate a browser that refuses to store the preview's cookies.
        client.cookies.clear()
        created = client.post("/api/operator/invites", json={"max_uses": 3}, headers={**ORIGIN, "X-CSRF-Token": csrf})

        assert created.status_code == 201
        assert created.json()["invite"]["max_uses"] == 3


def test_demo_mode_query_switch_selects_bootstrap_developer(tmp_path):
    settings = _settings(
        tmp_path,
        portal_bootstrap_operator_username="bootop",
        portal_bootstrap_operator_password="boot-oper-pass-1",
        portal_bootstrap_developer_username="bootdev",
        portal_bootstrap_developer_password="boot-dev-pass-1",
    )
    with _demo_client(settings) as client:
        operator_view = client.get("/api/session")
        developer_view = client.get("/api/session?as=developer")

        assert operator_view.json()["role"] == "operator"
        assert developer_view.status_code == 200
        assert developer_view.json()["role"] == "developer"


def test_demo_mode_off_by_default(tmp_path):
    with _demo_client(_settings(tmp_path, demo_mode=False)) as client:
        assert client.get("/api/session").status_code == 401


def test_explicit_login_takes_precedence_over_demo_binding(tmp_path):
    settings = _settings(tmp_path, portal_bootstrap_developer_username="bootdev", portal_bootstrap_developer_password="boot-dev-pass-1")
    with _demo_client(settings) as client:
        assert client.post("/auth/login", json={"username": "bootdev", "password": "boot-dev-pass-1"}, headers=ORIGIN).status_code == 200

        assert client.get("/api/session").json()["role"] == "developer"
