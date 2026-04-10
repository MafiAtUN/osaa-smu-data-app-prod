"""Authentication and password utilities for Streamlit pages."""

from __future__ import annotations

import base64
import hashlib
import hmac
import os
import secrets
import time

import streamlit as st


_HASH_PREFIX = "pbkdf2_sha256"
_HASH_ITERATIONS = 310_000
_LOCKOUT_CAP_SECONDS = 300


def hash_password(password: str, *, salt: str | None = None, iterations: int = _HASH_ITERATIONS) -> str:
    """Return a PBKDF2-SHA256 password hash string."""
    if not password:
        raise ValueError("Password cannot be empty.")

    salt_value = salt or secrets.token_hex(16)
    derived = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt_value.encode("utf-8"),
        iterations,
    )
    digest = base64.b64encode(derived).decode("ascii")
    return f"{_HASH_PREFIX}${iterations}${salt_value}${digest}"


def verify_password(password: str, stored_hash: str) -> bool:
    """Verify *password* against a PBKDF2-SHA256 hash string."""
    if not password or not stored_hash:
        return False

    try:
        algorithm, iterations_text, salt, expected_digest = stored_hash.split("$", 3)
        if algorithm != _HASH_PREFIX:
            return False
        candidate_hash = hash_password(password, salt=salt, iterations=int(iterations_text))
    except (TypeError, ValueError):
        return False

    return hmac.compare_digest(candidate_hash, stored_hash)


def password_matches(password: str, *, stored_hash: str = "", plain_text: str = "") -> bool:
    """Validate a password against a hash when available, falling back to plaintext."""
    if stored_hash:
        return verify_password(password, stored_hash)
    if plain_text:
        return hmac.compare_digest(password, plain_text)
    return False


def require_password(
    *,
    session_prefix: str,
    password_hash: str = "",
    plain_password: str = "",
    title: str = "Sign in required",
    help_text: str = "Enter the site password to continue.",
) -> bool:
    """Render a password gate and stop execution until the user is authenticated."""
    if not password_hash and not plain_password:
        return True

    auth_key = f"{session_prefix}_authenticated"
    attempts_key = f"{session_prefix}_failed_attempts"
    lockout_key = f"{session_prefix}_locked_until"
    message_key = f"{session_prefix}_auth_message"

    if st.session_state.get(auth_key):
        return True

    now = time.time()
    locked_until = float(st.session_state.get(lockout_key, 0.0) or 0.0)
    remaining = max(0, int(locked_until - now))

    st.title(title)
    st.write(help_text)

    if remaining > 0:
        st.error(f"Too many failed attempts. Try again in {remaining} seconds.")
    elif st.session_state.get(message_key):
        st.error(st.session_state[message_key])

    with st.form(f"{session_prefix}_login_form", clear_on_submit=True):
        password = st.text_input("Password", type="password", autocomplete="current-password")
        submitted = st.form_submit_button("Unlock", use_container_width=True, type="primary")

    if submitted:
        if locked_until > now:
            st.rerun()

        if password_matches(password, stored_hash=password_hash, plain_text=plain_password):
            st.session_state[auth_key] = True
            st.session_state[attempts_key] = 0
            st.session_state[lockout_key] = 0.0
            st.session_state[message_key] = ""
            st.rerun()

        failed_attempts = int(st.session_state.get(attempts_key, 0)) + 1
        lockout_seconds = min(2 ** min(failed_attempts, 8), _LOCKOUT_CAP_SECONDS)
        st.session_state[attempts_key] = failed_attempts
        st.session_state[lockout_key] = time.time() + lockout_seconds
        st.session_state[message_key] = "Incorrect password."
        st.rerun()

    st.stop()


def render_logout_button(*, session_prefix: str, label: str = "Log out") -> None:
    """Render a sidebar logout button for an authenticated scope."""
    auth_key = f"{session_prefix}_authenticated"
    if not st.session_state.get(auth_key):
        return

    if st.sidebar.button(label, use_container_width=True):
        st.session_state[auth_key] = False
        st.rerun()


def is_production_environment() -> bool:
    """Return True when running in a hosted or explicitly production environment."""
    return any(
        [
            os.getenv("APP_ENV", "").lower() == "production",
            os.getenv("ENVIRONMENT", "").lower() == "production",
            bool(os.getenv("RAILWAY_ENVIRONMENT")),
            bool(os.getenv("RAILWAY_PROJECT_ID")),
        ]
    )


def validate_runtime_security(*, password_hash: str = "", plain_password: str = "") -> None:
    """Fail closed when hosted with insecure authentication settings."""
    if not is_production_environment():
        return

    problems: list[str] = []
    cookie_secret = os.getenv("STREAMLIT_SERVER_COOKIE_SECRET", "")
    allow_plaintext = os.getenv("ALLOW_PLAINTEXT_PASSWORDS", "").lower() == "true"

    if not password_hash:
        problems.append("APP_PASSWORD_HASH must be set in production.")
    if plain_password and not allow_plaintext:
        problems.append("Plaintext app_password/APP_PASSWORD is not allowed in production.")
    if len(cookie_secret) < 32:
        problems.append("STREAMLIT_SERVER_COOKIE_SECRET must be set to a long random value in production.")

    if problems:
        st.error("Security configuration is incomplete:")
        for issue in problems:
            st.write(f"- {issue}")
        st.stop()
