"""Tests for app.core.config."""

import os
from unittest.mock import patch


def test_settings_loads_defaults():
    """Settings should have safe defaults even when no env vars are set."""
    with patch.dict(os.environ, {}, clear=True):
        from app.core.config import load_settings

        settings = load_settings()
        # Settings uses azure_accounts dict; check a well-known account default
        assert "osaa_v2" in settings.azure_accounts
        assert settings.azure_accounts["osaa_v2"].endpoint == "https://openai-osaa-v2.cognitiveservices.azure.com/"
        assert settings.acled.token_url == "https://acleddata.com/oauth/token"
        assert settings.sdg.api_url == "https://unstats.un.org/sdgs/UNSDGAPIV5"
        assert settings.app.password_hash == ""


def test_settings_reads_env():
    """Settings should pick up values from environment variables."""
    with patch.dict(
        os.environ,
        {
            "azure": "test-key-123",
            "acled_email": "a@b.com",
            "APP_PASSWORD_HASH": "pbkdf2_sha256$310000$salt$hash",
        },
        clear=False,
    ):
        from app.core.config import load_settings

        settings = load_settings()
        # "azure" env var populates the "osaa" account key
        assert settings.azure_accounts["osaa"].api_key == "test-key-123"
        assert settings.acled.email == "a@b.com"
        assert settings.app.password_hash == "pbkdf2_sha256$310000$salt$hash"
