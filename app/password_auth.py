"""Local password hashing and username policy."""

from argon2 import PasswordHasher, Type, extract_parameters
from argon2.exceptions import InvalidHashError, VerificationError, VerifyMismatchError


MIN_PASSWORD_LENGTH = 12
MAX_PASSWORD_BYTES = 1024
_hasher = PasswordHasher(time_cost=2, memory_cost=19_456, parallelism=1, hash_len=32, salt_len=16, type=Type.ID)
_dummy_hash = _hasher.hash("local-auth timing equalizer")


class PasswordPolicyError(ValueError):
    """Raised when a new password does not meet the local password bounds."""


def normalize_username(username: str) -> str:
    if not isinstance(username, str):
        raise ValueError("Username must be text")
    clean = username.strip()
    if not 3 <= len(clean) <= 32 or any(not (character.isascii() and (character.isalnum() or character in "._-")) for character in clean):
        raise ValueError("Username must be 3-32 ASCII letters, numbers, dots, underscores, or hyphens")
    return clean.casefold()


def validate_password(password: str) -> None:
    if not isinstance(password, str):
        raise PasswordPolicyError("Password must be text")
    if len(password) < MIN_PASSWORD_LENGTH:
        raise PasswordPolicyError(f"Password must be at least {MIN_PASSWORD_LENGTH} characters")
    try:
        encoded = password.encode("utf-8")
    except UnicodeEncodeError as exc:
        raise PasswordPolicyError("Password contains invalid Unicode") from exc
    if len(encoded) > MAX_PASSWORD_BYTES:
        raise PasswordPolicyError(f"Password must not exceed {MAX_PASSWORD_BYTES} UTF-8 bytes")


def hash_password(password: str) -> str:
    validate_password(password)
    return _hasher.hash(password)


def verify_password(password: str, encoded_hash: str) -> bool:
    if not isinstance(password, str) or not isinstance(encoded_hash, str) or not encoded_hash:
        return False
    try:
        return _hasher.verify(encoded_hash, password)
    except (VerifyMismatchError, VerificationError, InvalidHashError, ValueError):
        return False


def verify_password_or_dummy(password: str, encoded_hash: str | None) -> bool:
    if not encoded_hash:
        return _verify_dummy(password)
    try:
        extract_parameters(encoded_hash)
    except (InvalidHashError, VerificationError, TypeError, ValueError):
        return _verify_dummy(password)
    return verify_password(password, encoded_hash)


def _verify_dummy(password: str) -> bool:
    try:
        _hasher.verify(_dummy_hash, password)
    except (VerifyMismatchError, VerificationError, InvalidHashError, TypeError, ValueError):
        return False
    return False
