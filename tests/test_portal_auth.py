import base64
from concurrent.futures import ThreadPoolExecutor
import json
import sqlite3
import time
from urllib.parse import parse_qs, urlparse

import httpx
import pytest
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import padding, rsa
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.identity import HackClubOIDC
from app.portal_api import PortalService, create_portal_router
from app.portal_db import PortalDatabase


def _b64(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()


def _token(private_key, *, issuer="https://auth.hackclub.com", audience="portal-client", nonce="expected-nonce", exp=None):
    header = _b64(json.dumps({"alg": "RS256", "kid": "test-key", "typ": "JWT"}).encode())
    payload = _b64(json.dumps({
        "iss": issuer,
        "sub": "ident!member-1",
        "aud": audience,
        "exp": exp or int(time.time()) + 300,
        "iat": int(time.time()),
        "nonce": nonce,
        "name": "Member One",
        "email": "member@example.test",
        "email_verified": True,
    }).encode())
    signed = f"{header}.{payload}".encode()
    signature = private_key.sign(signed, padding.PKCS1v15(), hashes.SHA256())
    return f"{signed.decode()}.{_b64(signature)}"


@pytest.fixture
def signing_key():
    return rsa.generate_private_key(public_exponent=65537, key_size=2048)


def _jwk(public_key):
    numbers = public_key.public_numbers()
    return {"kty": "RSA", "use": "sig", "alg": "RS256", "kid": "test-key", "n": _b64(numbers.n.to_bytes((numbers.n.bit_length() + 7) // 8, "big")), "e": _b64(numbers.e.to_bytes((numbers.e.bit_length() + 7) // 8, "big"))}


@pytest.mark.parametrize("claims", [
    {"issuer": "https://attacker.example"},
    {"audience": "different-client"},
    {"nonce": "wrong-nonce"},
    {"exp": 1},
])
def test_id_token_rejects_invalid_claims(signing_key, claims):
    oidc = HackClubOIDC("client-id", "client-secret", "https://portal.example/auth/callback")
    token = _token(signing_key, **claims)
    with pytest.raises(ValueError):
        oidc.validate_id_token(token, expected_nonce="expected-nonce", jwks={"keys": [_jwk(signing_key.public_key())]})


def test_id_token_verifies_rs256_signature_and_returns_minimal_identity(signing_key):
    oidc = HackClubOIDC("portal-client", "secret", "https://portal.example/auth/callback")
    token = _token(signing_key)
    identity = oidc.validate_id_token(token, expected_nonce="expected-nonce", jwks={"keys": [_jwk(signing_key.public_key())]})
    assert identity.subject == "ident!member-1"
    assert identity.email == "member@example.test"
    assert identity.email_verified is True


def test_id_token_rejects_tampered_signature(signing_key):
    oidc = HackClubOIDC("portal-client", "secret", "https://portal.example/auth/callback")
    header, payload, signature = _token(signing_key).split(".")
    changed = ("A" if signature[0] != "A" else "B") + signature[1:]
    with pytest.raises(ValueError, match="signature"):
        oidc.validate_id_token(f"{header}.{payload}.{changed}", expected_nonce="expected-nonce", jwks={"keys": [_jwk(signing_key.public_key())]})


def test_identityless_runtime_does_not_mount_hca_callback(tmp_path):
    repo = PortalDatabase(str(tmp_path / "portal.db"), key_pepper="x" * 40)
    service = PortalService(repo, identity=None, cookie_secure=True)
    app = FastAPI()
    app.include_router(create_portal_router(service))

    with TestClient(app, base_url="https://portal.example") as client:
        assert client.get("/auth/callback").status_code == 404
        assert client.get("/auth/login").status_code == 405


def test_new_identity_without_invite_is_rejected_but_existing_user_can_sign_in(tmp_path):
    repo = PortalDatabase(str(tmp_path / "portal.db"), key_pepper="x" * 40)
    with pytest.raises(PermissionError, match="invitation"):
        repo.provision_identity(subject="new-subject", email="new@example.test", email_verified=True, name="New", invite_id=None)
    existing = repo.upsert_user(subject="existing-subject", email="old@example.test", name="Existing")
    authenticated = repo.provision_identity(subject="existing-subject", email="new@example.test", email_verified=True, name="Updated", invite_id=None)
    assert authenticated["id"] == existing["id"]
    assert authenticated["email"] == "new@example.test"


def test_invite_is_consumed_even_if_existing_identity_uses_it(tmp_path):
    repo = PortalDatabase(str(tmp_path / "portal.db"), key_pepper="x" * 40)
    operator = repo.upsert_user(subject="operator", email="operator@example.test", name="Operator", role="operator")
    invite, _raw = repo.create_invite(issuer_user_id=operator["id"], expires_in_seconds=600)
    existing = repo.upsert_user(subject="existing", email="existing@example.test", name="Existing")
    signed_in = repo.provision_identity(subject="existing", email="existing@example.test", email_verified=True, name="Existing", invite_id=invite["id"])
    assert signed_in["id"] == existing["id"]
    assert repo.list_invites()[0]["consumed_at"] is not None
    assert repo.list_invites()[0]["uses_count"] == 1
    with pytest.raises(PermissionError, match="invalid|expired|used"):
        repo.provision_identity(subject="new", email="new@example.test", email_verified=True, name="New", invite_id=invite["id"])


def test_initial_operator_bootstrap_requires_verified_configured_email_and_is_one_time(tmp_path):
    repo = PortalDatabase(str(tmp_path / "portal.db"), key_pepper="x" * 40)
    with pytest.raises(PermissionError):
        repo.bootstrap_operator(verified_subject="ident!attacker", verified_email="attacker@example.test", email_verified=True, configured_email="owner@example.test", name="Attacker")
    with pytest.raises(PermissionError):
        repo.bootstrap_operator(verified_subject="ident!owner", verified_email="owner@example.test", email_verified=False, configured_email="owner@example.test", name="Owner")
    operator = repo.bootstrap_operator(verified_subject="ident!owner", verified_email="Owner@example.test", email_verified=True, configured_email="owner@example.test", name="Owner")
    assert operator["role"] == "operator"
    with pytest.raises(PermissionError):
        repo.bootstrap_operator(verified_subject="ident!other", verified_email="other@example.test", email_verified=True, configured_email="other@example.test", name="Other")


def test_local_usernames_are_unique_case_insensitively_and_account_creation_consumes_invite(tmp_path):
    repo = PortalDatabase(str(tmp_path / "portal.db"), key_pepper="x" * 40)
    operator = repo.upsert_user(subject="operator", email="operator@example.test", name="Operator", role="operator")
    invite, raw = repo.create_invite(issuer_user_id=operator["id"], max_uses=3)

    first = repo.create_local_account_with_invite(
        raw_token=raw, username="River", password_hash="argon2id$hash-1", display_name="River One"
    )
    second = repo.create_local_account_with_invite(
        raw_token=raw, username="Other", password_hash="argon2id$hash-2", display_name="River Two"
    )

    assert first["username"] == "River"
    assert first["username_normalized"] == "river"
    assert first["oidc_subject"] is None
    assert first["password_hash"] == "argon2id$hash-1"
    assert second["id"] != first["id"]
    with pytest.raises((ValueError, sqlite3.IntegrityError), match="[Uu]sername|unique"):
        repo.create_local_account_with_invite(
            raw_token=raw, username="rIvEr", password_hash="argon2id$hash-3", display_name="Duplicate"
        )
    with repo.connect() as connection:
        assert connection.execute("SELECT COUNT(*) FROM portal_users WHERE username IS NOT NULL").fetchone()[0] == 2
    listed = next(item for item in repo.list_invites() if item["id"] == invite["id"])
    assert listed["uses_count"] == 2
    assert listed["max_uses"] == 3
    assert listed["consumed_at"] is None


def test_developer_can_issue_exactly_one_single_use_invite(tmp_path):
    repo = PortalDatabase(str(tmp_path / "portal.db"), key_pepper="x" * 40)
    developer = repo.upsert_user(subject="developer", email="dev@example.test", name="Dev")

    invite, raw = repo.create_developer_invite(issuer_user_id=developer["id"])
    assert repo.find_invite(raw)["id"] == invite["id"]
    assert invite["max_uses"] == 1
    with pytest.raises(PermissionError, match="entitlement|already issued"):
        repo.create_developer_invite(issuer_user_id=developer["id"])

    account = repo.create_local_account_with_invite(
        raw_token=raw, username="child", password_hash="argon2id$child", display_name="Child"
    )
    assert account["role"] == "developer"
    assert repo.find_invite(raw) is None


@pytest.mark.parametrize("invalidity", ["expired", "revoked", "exhausted"])
def test_local_signup_rejects_expired_revoked_or_exhausted_invites(tmp_path, invalidity):
    repo = PortalDatabase(str(tmp_path / f"{invalidity}.db"), key_pepper="x" * 40)
    operator = repo.upsert_user(subject="operator", email="operator@example.test", name="Operator", role="operator")
    invite, raw = repo.create_invite(issuer_user_id=operator["id"], expires_in_seconds=60)
    with repo.connect() as connection:
        if invalidity == "expired":
            connection.execute("UPDATE portal_invites SET expires_at='2000-01-01T00:00:00+00:00' WHERE id=?", (invite["id"],))
        elif invalidity == "revoked":
            repo.revoke_invite(invite["id"], revoked_by_user_id=operator["id"])
        else:
            connection.execute("UPDATE portal_invites SET uses_count=max_uses WHERE id=?", (invite["id"],))

    with pytest.raises(PermissionError, match="invalid|expired|revoked|used|exhausted"):
        repo.create_local_account_with_invite(
            raw_token=raw, username="blocked", password_hash="argon2id$blocked", display_name="Blocked"
        )


def test_concurrent_signups_never_exceed_five_invite_uses(tmp_path):
    repo = PortalDatabase(str(tmp_path / "portal.db"), key_pepper="x" * 40)
    operator = repo.upsert_user(subject="operator", email="operator@example.test", name="Operator", role="operator")
    invite, raw = repo.create_invite(issuer_user_id=operator["id"], max_uses=5)

    def signup(number):
        try:
            repo.create_local_account_with_invite(
                raw_token=raw, username=f"member{number}", password_hash=f"argon2id$hash-{number}", display_name=f"Member {number}"
            )
            return True
        except PermissionError:
            return False

    with ThreadPoolExecutor(max_workers=12) as pool:
        created = list(pool.map(signup, range(12)))

    assert sum(created) == 5
    assert len([user for user in repo.list_users() if user["display_name"].startswith("Member ")]) == 5
    final = next(item for item in repo.list_invites() if item["id"] == invite["id"])
    assert final["uses_count"] == final["max_uses"] == 5


def test_failed_local_account_insert_rolls_back_invite_use(tmp_path):
    repo = PortalDatabase(str(tmp_path / "portal.db"), key_pepper="x" * 40)
    operator = repo.upsert_user(subject="operator", email="operator@example.test", name="Operator", role="operator")
    invite, raw = repo.create_invite(issuer_user_id=operator["id"], max_uses=2)
    with pytest.raises(ValueError, match="username"):
        repo.create_local_account_with_invite(raw_token=raw, username="  ", password_hash="hash", display_name="Invalid")
    current = next(item for item in repo.list_invites() if item["id"] == invite["id"])
    assert current["uses_count"] == 0


def test_local_signup_rejects_bound_email_invite_without_account_or_quota_change(tmp_path):
    repo = PortalDatabase(str(tmp_path / "portal.db"), key_pepper="x" * 40)
    operator = repo.upsert_user(subject="operator", email="operator@example.test", name="Operator", role="operator")
    invite, raw = repo.create_invite(
        issuer_user_id=operator["id"], bound_email="person@example.test", max_uses=3
    )

    with repo.connect() as connection:
        user_count_before = connection.execute("SELECT COUNT(*) FROM portal_users").fetchone()[0]
    with pytest.raises(PermissionError, match="verified email|bound"):
        repo.create_local_account_with_invite(
            raw_token=raw, username="bound-person", password_hash="argon2id$hash", display_name="Bound Person"
        )

    with repo.connect() as connection:
        user_count_after = connection.execute("SELECT COUNT(*) FROM portal_users").fetchone()[0]
        invite_after = connection.execute(
            "SELECT uses_count,max_uses,consumed_at,revoked_at FROM portal_invites WHERE id=?", (invite["id"],)
        ).fetchone()
    assert user_count_after == user_count_before
    assert tuple(invite_after) == (0, 3, None, None)
    assert repo.find_invite(raw)["id"] == invite["id"]
