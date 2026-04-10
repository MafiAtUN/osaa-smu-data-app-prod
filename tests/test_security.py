"""Tests for password hashing helpers."""

from app.core.security import hash_password, password_matches, verify_password


def test_hash_password_verifies_correctly():
    password = "StrongPassw0rd!"
    stored_hash = hash_password(password, salt="fixedsalt", iterations=1000)

    assert verify_password(password, stored_hash)
    assert not verify_password("wrong-password", stored_hash)


def test_password_matches_supports_plaintext_fallback():
    assert password_matches("abc123", plain_text="abc123")
    assert not password_matches("abc123", plain_text="xyz789")
