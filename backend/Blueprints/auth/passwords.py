import hashlib

from werkzeug.security import check_password_hash, generate_password_hash
LEGACY_SHA256_LENGTH = 64


def hash_password(password):
    return generate_password_hash(password)


def verify_password(stored_hash, password):
    if not stored_hash or not password:
        return False

    if is_legacy_sha256_hash(stored_hash):
        return stored_hash == legacy_sha256(password)

    return check_password_hash(stored_hash, password)


def needs_password_rehash(stored_hash):
    return is_legacy_sha256_hash(stored_hash)


def is_legacy_sha256_hash(value):
    return (
        len(value) == LEGACY_SHA256_LENGTH
        and all(char in "0123456789abcdef" for char in value)
    )


def legacy_sha256(password):
    return hashlib.sha256(password.encode("utf-8")).hexdigest()
