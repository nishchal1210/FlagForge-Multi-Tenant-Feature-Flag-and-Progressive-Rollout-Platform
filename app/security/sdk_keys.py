import hashlib
import hmac
import secrets
import uuid


def generate_sdk_key(
    key_id: uuid.UUID,
) -> tuple[str, str]:
    secret = secrets.token_urlsafe(32) # creates a random secret

    plain_key = (
        f"ff_env_{key_id.hex}_{secret}"
    )
    # ff = flagforge
    # env = environment scope dkey
    # uuid: identify the db record
    # proves that caller owns the key

    key_hash = hash_sdk_key(plain_key)

    return plain_key, key_hash


def hash_sdk_key(plain_key: str) -> str:
    return hashlib.sha256(
        plain_key.encode("utf-8")
    ).hexdigest()
# This creates a 64-character hexadecimal SHA-256 digest.


def verify_sdk_key(
    plain_key: str,
    expected_hash: str,
) -> bool:
    actual_hash = hash_sdk_key(plain_key)

    return hmac.compare_digest(
        actual_hash,
        expected_hash,
    )


def extract_key_id(
    plain_key: str,
) -> uuid.UUID | None:
    parts = plain_key.split("_", 3)

    if len(parts) != 4:
        return None

    if parts[0] != "ff" or parts[1] != "env":
        return None

    try:
        return uuid.UUID(hex=parts[2])
    except ValueError:
        return None