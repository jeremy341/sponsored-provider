"""Hack Club OpenID Connect primitives with pinned trust and strict RS256 checks."""

from __future__ import annotations

import base64
import json
import time
from dataclasses import dataclass
from typing import Any
from urllib.parse import urlencode, urlparse

import httpx
from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import padding, rsa


HACKCLUB_ISSUER = "https://auth.hackclub.com"
HACKCLUB_DISCOVERY = f"{HACKCLUB_ISSUER}/.well-known/openid-configuration"
_CLOCK_SKEW_SECONDS = 60
_MAX_JWT_BYTES = 64 * 1024


@dataclass(frozen=True)
class PortalIdentity:
    subject: str
    email: str | None
    email_verified: bool
    name: str


def _decode_segment(segment: str) -> bytes:
    if not segment or len(segment) > _MAX_JWT_BYTES:
        raise ValueError("Malformed ID token")
    try:
        return base64.urlsafe_b64decode(segment + "=" * (-len(segment) % 4))
    except (ValueError, TypeError) as exc:
        raise ValueError("Malformed ID token") from exc


def _json_segment(segment: str) -> dict[str, Any]:
    try:
        value = json.loads(_decode_segment(segment))
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise ValueError("Malformed ID token") from exc
    if not isinstance(value, dict):
        raise ValueError("Malformed ID token")
    return value


class HackClubOIDC:
    """OAuth code exchange and ID-token verifier for Hack Club Auth.

    The issuer is intentionally fixed to Hack Club Auth. Discovery metadata is
    still checked at runtime, and every endpoint must remain HTTPS on that exact
    origin. Only RS256 ID tokens are accepted, matching Hack Club's OIDC guide.
    """

    def __init__(
        self,
        client_id: str,
        client_secret: str,
        redirect_uri: str,
        *,
        issuer: str = HACKCLUB_ISSUER,
        transport: httpx.AsyncBaseTransport | None = None,
        timeout_seconds: float = 8.0,
    ):
        if issuer != HACKCLUB_ISSUER:
            raise ValueError("Only the configured Hack Club Auth issuer is trusted")
        if not client_id or not client_secret:
            raise ValueError("Hack Club OAuth client credentials are required")
        parsed = urlparse(redirect_uri)
        if parsed.scheme != "https" or not parsed.netloc or parsed.username or parsed.password or parsed.fragment:
            raise ValueError("The OIDC redirect URI must be an absolute HTTPS URL without credentials or fragment")
        self.client_id = client_id
        self.client_secret = client_secret
        self.redirect_uri = redirect_uri
        self.issuer = issuer
        self.transport = transport
        self.timeout_seconds = timeout_seconds
        self._metadata: dict[str, Any] | None = None
        self._metadata_cached_at = 0.0
        self._jwks: dict[str, Any] | None = None
        self._jwks_cached_at = 0.0

    @staticmethod
    def _trusted_endpoint(value: Any) -> str:
        if not isinstance(value, str):
            raise ValueError("Invalid OIDC discovery endpoint")
        parsed = urlparse(value)
        if parsed.scheme != "https" or parsed.hostname != "auth.hackclub.com" or parsed.port not in (None, 443) or parsed.username or parsed.password:
            raise ValueError("OIDC discovery returned an untrusted endpoint")
        return value

    async def discovery(self, *, force_refresh: bool = False) -> dict[str, Any]:
        if self._metadata and not force_refresh and time.monotonic() - self._metadata_cached_at < 300:
            return self._metadata
        async with httpx.AsyncClient(timeout=self.timeout_seconds, transport=self.transport, follow_redirects=False) as client:
            response = await client.get(HACKCLUB_DISCOVERY)
            response.raise_for_status()
            metadata = response.json()
        if not isinstance(metadata, dict) or metadata.get("issuer") != self.issuer:
            raise ValueError("Hack Club Auth discovery issuer did not match the pinned issuer")
        if "code" not in metadata.get("response_types_supported", ["code"]):
            raise ValueError("Hack Club Auth discovery does not support authorization code flow")
        if "RS256" not in metadata.get("id_token_signing_alg_values_supported", ["RS256"]):
            raise ValueError("Hack Club Auth discovery does not advertise RS256 ID tokens")
        for field in ("authorization_endpoint", "token_endpoint", "jwks_uri"):
            self._trusted_endpoint(metadata.get(field))
        self._metadata = metadata
        self._metadata_cached_at = time.monotonic()
        return metadata

    async def authorization_url(self, *, state: str, nonce: str) -> str:
        metadata = await self.discovery()
        params = {
            "client_id": self.client_id,
            "redirect_uri": self.redirect_uri,
            "response_type": "code",
            "scope": "openid profile email",
            "state": state,
            "nonce": nonce,
        }
        return f"{metadata['authorization_endpoint']}?{urlencode(params)}"

    async def exchange_code(self, code: str) -> str:
        if not code or len(code) > 4096:
            raise ValueError("Invalid OAuth authorization code")
        metadata = await self.discovery()
        async with httpx.AsyncClient(timeout=self.timeout_seconds, transport=self.transport, follow_redirects=False) as client:
            response = await client.post(
                metadata["token_endpoint"],
                data={
                    "grant_type": "authorization_code",
                    "client_id": self.client_id,
                    "client_secret": self.client_secret,
                    "redirect_uri": self.redirect_uri,
                    "code": code,
                },
                headers={"Accept": "application/json"},
            )
            response.raise_for_status()
            data = response.json()
        if not isinstance(data, dict) or not isinstance(data.get("id_token"), str):
            raise ValueError("Hack Club Auth did not return an ID token")
        return data["id_token"]

    async def signing_keys(self, *, force_refresh: bool = False) -> dict[str, Any]:
        if self._jwks and not force_refresh and time.monotonic() - self._jwks_cached_at < 300:
            return self._jwks
        metadata = await self.discovery()
        async with httpx.AsyncClient(timeout=self.timeout_seconds, transport=self.transport, follow_redirects=False) as client:
            response = await client.get(metadata["jwks_uri"])
            response.raise_for_status()
            jwks = response.json()
        if not isinstance(jwks, dict) or not isinstance(jwks.get("keys"), list):
            raise ValueError("Hack Club Auth returned an invalid JWKS")
        self._jwks = jwks
        self._jwks_cached_at = time.monotonic()
        return jwks

    def validate_id_token(self, token: str, *, expected_nonce: str, jwks: dict[str, Any]) -> PortalIdentity:
        if not isinstance(token, str) or len(token) > _MAX_JWT_BYTES:
            raise ValueError("Malformed ID token")
        parts = token.split(".")
        if len(parts) != 3:
            raise ValueError("Malformed ID token")
        header = _json_segment(parts[0])
        claims = _json_segment(parts[1])
        if header.get("alg") != "RS256" or not isinstance(header.get("kid"), str) or header.get("crit"):
            raise ValueError("Unsupported ID token signing algorithm or header")
        key = next((item for item in jwks.get("keys", []) if isinstance(item, dict) and item.get("kid") == header["kid"]), None)
        if not key or key.get("kty") != "RSA" or key.get("use", "sig") != "sig" or key.get("alg", "RS256") != "RS256":
            raise ValueError("No trusted RS256 signing key matches this ID token")
        try:
            modulus = int.from_bytes(_decode_segment(key["n"]), "big")
            exponent = int.from_bytes(_decode_segment(key["e"]), "big")
            public_key = rsa.RSAPublicNumbers(exponent, modulus).public_key()
            public_key.verify(_decode_segment(parts[2]), f"{parts[0]}.{parts[1]}".encode("ascii"), padding.PKCS1v15(), hashes.SHA256())
        except (KeyError, TypeError, ValueError, InvalidSignature) as exc:
            raise ValueError("ID token signature verification failed") from exc

        now = time.time()
        issuer = claims.get("iss")
        audience = claims.get("aud")
        audiences = [audience] if isinstance(audience, str) else audience if isinstance(audience, list) else []
        if issuer != self.issuer or self.client_id not in audiences:
            raise ValueError("ID token issuer or audience is invalid")
        if len(audiences) > 1 and claims.get("azp") != self.client_id:
            raise ValueError("ID token authorized party is invalid")
        exp = claims.get("exp")
        issued = claims.get("iat")
        not_before = claims.get("nbf", 0)
        if not isinstance(exp, (int, float)) or isinstance(exp, bool) or exp <= now - _CLOCK_SKEW_SECONDS:
            raise ValueError("ID token is expired or missing a valid expiry")
        if not isinstance(issued, (int, float)) or isinstance(issued, bool) or issued > now + _CLOCK_SKEW_SECONDS:
            raise ValueError("ID token issue time is invalid")
        if not isinstance(not_before, (int, float)) or isinstance(not_before, bool) or not_before > now + _CLOCK_SKEW_SECONDS:
            raise ValueError("ID token is not yet valid")
        subject = claims.get("sub")
        if not isinstance(subject, str) or not subject or len(subject) > 255:
            raise ValueError("ID token subject is invalid")
        if not isinstance(expected_nonce, str) or not expected_nonce or not isinstance(claims.get("nonce"), str) or not __import__("hmac").compare_digest(claims["nonce"], expected_nonce):
            raise ValueError("ID token nonce is invalid")
        email = claims.get("email")
        if email is not None and (not isinstance(email, str) or len(email) > 320):
            email = None
        return PortalIdentity(
            subject=subject,
            email=email,
            email_verified=claims.get("email_verified") is True,
            name=(claims.get("name") if isinstance(claims.get("name"), str) else "")[:160],
        )
