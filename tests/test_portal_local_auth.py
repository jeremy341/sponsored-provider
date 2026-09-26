import hashlib

from fastapi import FastAPI
from fastapi.testclient import TestClient
from cryptography.fernet import Fernet

from app.password_auth import PasswordPolicyError, hash_password, verify_password
import app.password_auth as password_auth
import pytest
from app.portal_api import PortalService, create_portal_router
from app.portal_db import PortalDatabase
from app.cli import bootstrap_local_operator, operator_reset_password


ORIGIN = {"Origin": "https://portal.example"}


def _local_app(tmp_path, *, secure=False, attempts=5):
    repository = PortalDatabase(str(tmp_path / "portal.db"), key_pepper="p" * 40)
    operator = repository.upsert_user(
        subject="bootstrap-test-operator", email="operator@example.test", name="Operator", role="operator"
    )
    invite, token = repository.create_invite(issuer_user_id=operator["id"], max_uses=3)
    service = PortalService(
        repository,
        identity=None,
        cookie_secure=secure,
        auth_rate_limit_attempts=attempts,
        auth_rate_limit_window_seconds=900,
        public_origin="https://portal.example",
    )
    app = FastAPI()
    app.include_router(create_portal_router(service))
    return TestClient(app, base_url="https://portal.example" if secure else "http://portal.example"), repository, token, invite


def test_password_hash_uses_argon2id_and_verifies_password():
    encoded = hash_password("correct horse battery staple")

    assert encoded.startswith("$argon2id$")
    assert verify_password("correct horse battery staple", encoded)
    assert not verify_password("wrong password", encoded)


def test_password_verification_rejects_empty_or_malformed_hashes():
    assert not verify_password("local-auth timing equalizer", "")
    assert not verify_password("correct horse battery staple", "not-an-argon2-hash")


def test_malformed_stored_hash_performs_dummy_argon2_work(monkeypatch):
    work = []
    monkeypatch.setattr(password_auth, "_verify_dummy", lambda password: work.append(password) or False)

    assert not password_auth.verify_password_or_dummy("candidate password", "malformed stored hash")
    assert work == ["candidate password"]


def test_password_policy_rejects_short_and_oversized_passwords():
    for password in ("short", "x" * 1025):
        try:
            hash_password(password)
        except PasswordPolicyError:
            pass
        else:
            raise AssertionError("password outside the documented bounds was accepted")


def test_local_signup_requires_invite_and_creates_an_authenticated_session(tmp_path):
    client, repository, invite, _ = _local_app(tmp_path)

    denied = client.post("/auth/signup", json={"username": "new-user", "password": "correct horse battery staple", "invite": "invalid"}, headers=ORIGIN)
    assert denied.status_code == 403
    assert client.post("/auth/signup", json={"username": "new-user", "password": "correct horse battery staple"}, headers=ORIGIN).status_code == 422

    created = client.post("/auth/signup", json={"username": "New-User", "password": "correct horse battery staple", "invite": invite}, headers=ORIGIN)
    assert created.status_code == 201
    assert created.json()["role"] == "developer"
    assert client.get("/api/session").json()["user"]["username"] == "New-User"
    account = repository.get_local_user_by_username("new-user")
    assert account["username_normalized"] == "new-user"
    assert account["password_hash"].startswith("$argon2id$")


def test_login_uses_same_error_for_unknown_username_and_wrong_password(tmp_path):
    client, _repository, invite, _ = _local_app(tmp_path)
    client.post("/auth/signup", json={"username": "Known-User", "password": "correct horse battery staple", "invite": invite}, headers=ORIGIN)
    client.cookies.clear()

    wrong = client.post("/auth/login", json={"username": "known-user", "password": "incorrect password"}, headers=ORIGIN)
    unknown = client.post("/auth/login", json={"username": "missing-user", "password": "incorrect password"}, headers=ORIGIN)

    assert wrong.status_code == unknown.status_code == 401
    assert wrong.json() == unknown.json() == {"detail": "Invalid username or password"}


def test_login_rotates_existing_session_and_sets_expected_cookie_attributes(tmp_path):
    client, repository, invite, _ = _local_app(tmp_path, secure=True)
    client.post("/auth/signup", json={"username": "cookie-user", "password": "correct horse battery staple", "invite": invite}, headers=ORIGIN)
    old_token = client.cookies.get("portal_session")

    response = client.post("/auth/login", json={"username": "COOKIE-USER", "password": "correct horse battery staple"}, headers=ORIGIN)

    assert response.status_code == 200
    assert client.cookies.get("portal_session") != old_token
    assert repository.get_session(old_token) is None
    cookies = response.headers.get_list("set-cookie")
    session_cookie = next(value for value in cookies if value.startswith("portal_session="))
    csrf_cookie = next(value for value in cookies if value.startswith("portal_csrf="))
    assert "httponly" in session_cookie.lower() and "secure" in session_cookie.lower() and "samesite=lax" in session_cookie.lower()
    assert "secure" in csrf_cookie.lower() and "httponly" not in csrf_cookie.lower()


def test_local_auth_rejects_cross_origin_posts_and_logout_requires_csrf(tmp_path):
    client, _repository, invite, _ = _local_app(tmp_path)
    cross_origin = {"Origin": "https://attacker.example"}
    assert client.post("/auth/signup", json={"username": "blocked-user", "password": "correct horse battery staple", "invite": invite}, headers=cross_origin).status_code == 403

    created = client.post("/auth/signup", json={"username": "logout-user", "password": "correct horse battery staple", "invite": invite}, headers=ORIGIN)
    assert created.status_code == 201
    assert client.post("/auth/logout", headers={**ORIGIN, "X-CSRF-Token": "wrong"}).status_code == 403
    csrf = client.cookies.get("portal_csrf")
    session_token = client.cookies.get("portal_session")
    logged_out = client.post("/auth/logout", headers={**ORIGIN, "X-CSRF-Token": csrf})
    assert logged_out.status_code == 204
    assert client.get("/api/session").status_code == 401


def test_auth_rate_limit_is_persistent_and_scoped_by_normalized_username_and_client_ip(tmp_path):
    client, repository, invite, _ = _local_app(tmp_path, attempts=2)
    payload = {"username": " Rate-User ", "password": "wrong password"}
    assert client.post("/auth/login", json=payload, headers=ORIGIN).status_code == 401
    assert client.post("/auth/login", json={**payload, "username": "rate-user"}, headers=ORIGIN).status_code == 401
    assert client.post("/auth/login", json=payload, headers=ORIGIN).status_code == 429

    restarted = PortalService(repository, identity=None, cookie_secure=False, auth_rate_limit_attempts=2, auth_rate_limit_window_seconds=900, public_origin="https://portal.example")
    other_app = FastAPI()
    other_app.include_router(create_portal_router(restarted))
    assert TestClient(other_app, base_url="http://portal.example").post("/auth/signup", json={"username": "RATE-USER", "password": "correct horse battery staple", "invite": invite}, headers=ORIGIN).status_code == 429


def test_operator_invite_api_accepts_max_uses_and_developer_can_issue_one_invite(tmp_path):
    client, repository, _invite, _ = _local_app(tmp_path)
    operator = repository.upsert_user(subject="api-operator", email="api-operator@example.test", name="Operator", role="operator")
    operator_session = repository.create_session(operator["id"])
    client.cookies.set("portal_session", operator_session.raw_token)
    client.cookies.set("portal_csrf", operator_session.csrf_token)
    headers = {**ORIGIN, "X-CSRF-Token": operator_session.csrf_token}

    issued = client.post("/api/operator/invites", json={"expires_in_seconds": 3600, "max_uses": 4}, headers=headers)
    assert issued.status_code == 201
    record = repository.find_invite(issued.json()["invite_token"])
    assert record["max_uses"] == 4

    client.cookies.clear()
    client.post("/auth/signup", json={"username": "developer", "password": "correct horse battery staple", "invite": record and issued.json()["invite_token"]}, headers=ORIGIN)
    csrf = client.cookies.get("portal_csrf")
    first = client.post("/api/developer/invites", json={"expires_in_seconds": 3600}, headers={**ORIGIN, "X-CSRF-Token": csrf})
    second = client.post("/api/developer/invites", json={"expires_in_seconds": 3600}, headers={**ORIGIN, "X-CSRF-Token": csrf})
    assert first.status_code == 201
    assert repository.find_invite(first.json()["invite_token"])["max_uses"] == 1
    assert second.status_code == 409


def test_active_router_does_not_register_hca_routes(tmp_path):
    client, _repository, _invite, _ = _local_app(tmp_path)
    assert client.get("/auth/callback").status_code == 404
    assert client.post("/auth/callback").status_code == 404
    assert client.post("/auth/adopt-operator").status_code == 404
    assert client.post("/api/operator/adopt-operator").status_code == 404


def test_cli_bootstrap_creates_only_the_first_operator(tmp_path):
    repository = PortalDatabase(str(tmp_path / "portal.db"), key_pepper="p" * 40)
    assert bootstrap_local_operator is not None

    created = bootstrap_local_operator(repository, "First-Operator", "correct horse battery staple")

    assert created["role"] == "operator"
    assert created["username_normalized"] == "first-operator"
    try:
        bootstrap_local_operator(repository, "Second-Operator", "correct horse battery staple")
    except PermissionError:
        pass
    else:
        raise AssertionError("bootstrap created a second operator")


def test_operator_assisted_reset_changes_password_and_revokes_all_sessions(tmp_path):
    repository = PortalDatabase(str(tmp_path / "portal.db"), key_pepper="p" * 40)
    assert bootstrap_local_operator is not None and operator_reset_password is not None
    operator = bootstrap_local_operator(repository, "Operator", "operator password long enough")
    developer_invite, raw = repository.create_invite(issuer_user_id=operator["id"])
    developer = repository.create_local_account_with_invite(
        raw_token=raw, username="reset-target", password_hash=hash_password("old password long enough"), display_name="Target"
    )
    session = repository.create_session(developer["id"])

    operator_reset_password(repository, "operator", "operator password long enough", "reset-target", "new password long enough")

    assert repository.get_session(session.raw_token) is None
    changed = repository.get_local_user_by_username("reset-target")
    assert verify_password("new password long enough", changed["password_hash"])
    assert not verify_password("old password long enough", changed["password_hash"])


def test_operator_reset_requires_valid_operator_credentials(tmp_path):
    repository = PortalDatabase(str(tmp_path / "portal.db"), key_pepper="p" * 40)
    assert bootstrap_local_operator is not None and operator_reset_password is not None
    bootstrap_local_operator(repository, "Operator", "operator password long enough")

    try:
        operator_reset_password(repository, "operator", "wrong operator password", "missing-user", "new password long enough")
    except PermissionError:
        pass
    else:
        raise AssertionError("reset proceeded without operator authentication")


def test_main_startup_serves_local_auth_without_oauth_and_does_not_mount_hca(tmp_path):
    from fastapi import FastAPI
    from app.config import Settings, get_settings
    from app.main import get_portal_db, lifespan

    settings = Settings(
        database_path=str(tmp_path / "provider.db"),
        provider_key_pepper="p" * 40,
        provider_secret_key=Fernet.generate_key().decode(),
    )
    local_app = FastAPI(lifespan=lifespan)
    local_app.dependency_overrides[get_settings] = lambda: settings
    repository = get_portal_db(settings)
    operator = repository.upsert_user(subject="operator-before-startup", email="op@example.test", name="Operator", role="operator")
    _record, invite = repository.create_invite(issuer_user_id=operator["id"])

    with TestClient(local_app, base_url="https://portal.example") as client:
        response = client.post("/auth/signup", json={"username": "secure-default", "password": "correct horse battery staple", "invite": invite}, headers=ORIGIN)
        assert response.status_code == 201
        session_cookie = next(value for value in response.headers.get_list("set-cookie") if value.startswith("portal_session="))
        assert "secure" in session_cookie.lower()
        assert client.get("/auth/callback").status_code == 404
        assert local_app.state.portal_enabled is True


def test_cookie_security_defaults_on_and_can_be_disabled_for_local_http(tmp_path, monkeypatch):
    from app.config import Settings

    defaults = Settings(database_path=str(tmp_path / "default.db"), provider_key_pepper="p" * 40, _env_file=None)
    monkeypatch.setenv("PORTAL_COOKIE_SECURE", "false")
    local_http = Settings(database_path=str(tmp_path / "http.db"), provider_key_pepper="p" * 40, _env_file=None)

    assert defaults.portal_cookie_secure is True
    assert local_http.portal_cookie_secure is False


def test_existing_hca_operator_can_be_adopted_without_changing_identity_or_history(tmp_path):
    from app import cli

    repository = PortalDatabase(str(tmp_path / "portal.db"), key_pepper="p" * 40)
    legacy = repository.upsert_user(subject="hca-operator-subject", email="legacy@example.test", name="Legacy operator", role="operator")
    before = {key: legacy[key] for key in ("id", "oidc_subject", "role", "created_at", "last_login_at")}
    adopt = getattr(cli, "adopt_local_operator", None)
    assert callable(adopt)
    with pytest.raises(PermissionError):
        bootstrap_local_operator(repository, "second-operator", "second operator password long enough")

    adopted = adopt(repository, legacy["id"], "adopted-operator", "operator password long enough")

    assert {key: adopted[key] for key in before} == before
    assert adopted["username_normalized"] == "adopted-operator"
    assert verify_password("operator password long enough", adopted["password_hash"])


def test_operator_adoption_refuses_existing_local_credentials_and_non_operators(tmp_path):
    from app import cli

    repository = PortalDatabase(str(tmp_path / "portal.db"), key_pepper="p" * 40)
    adopt = getattr(cli, "adopt_local_operator", None)
    assert callable(adopt)
    operator = bootstrap_local_operator(repository, "Existing-Operator", "operator password long enough")
    _developer_invite, raw = repository.create_invite(issuer_user_id=operator["id"])
    developer = repository.create_local_account_with_invite(
        raw_token=raw, username="existing-developer", password_hash=hash_password("developer password long enough"), display_name="Developer"
    )

    with pytest.raises(PermissionError):
        adopt(repository, operator["id"], "replacement", "replacement password long enough")
    with pytest.raises(PermissionError):
        adopt(repository, developer["id"], "not-operator", "replacement password long enough")


def test_cli_exposes_operator_adoption_without_http_route(tmp_path, monkeypatch, capsys):
    from app import cli
    from app.config import Settings

    settings = Settings(database_path=str(tmp_path / "provider.db"), provider_key_pepper="p" * 40)
    portal_pepper = hashlib.sha256(("sponsored-provider:portal:v1:" + settings.provider_key_pepper).encode()).hexdigest()
    repository = PortalDatabase(settings.database_path, key_pepper=portal_pepper)
    legacy = repository.upsert_user(subject="hca-operator", email="legacy@example.test", name="Legacy", role="operator")
    prompts = iter(["operator password long enough", "operator password long enough"])
    monkeypatch.setattr(cli, "get_settings", lambda: settings)
    monkeypatch.setattr(cli.getpass, "getpass", lambda _prompt: next(prompts))
    monkeypatch.setattr("builtins.input", lambda _prompt: "legacy-user")
    monkeypatch.setattr("sys.argv", ["provider", "auth", "adopt-operator", "--user-id", legacy["id"]])

    cli.main()

    assert "Operator account adopted." in capsys.readouterr().out
    assert repository.get_user(legacy["id"])["oidc_subject"] == "hca-operator"


def test_cli_bootstrap_prompts_for_password_without_echoing_it(tmp_path, monkeypatch, capsys):
    from app import cli
    from app.config import Settings

    settings = Settings(database_path=str(tmp_path / "provider.db"), provider_key_pepper="p" * 40)
    prompts = iter(["correct horse battery staple", "correct horse battery staple"])
    monkeypatch.setattr(cli, "get_settings", lambda: settings)
    monkeypatch.setattr("builtins.input", lambda _prompt: "First-Operator")
    monkeypatch.setattr(cli.getpass, "getpass", lambda _prompt: next(prompts))
    monkeypatch.setattr("sys.argv", ["provider", "auth", "bootstrap"])

    cli.main()

    output = capsys.readouterr().out
    assert "First operator created." in output
    assert "correct horse battery staple" not in output
