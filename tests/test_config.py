"""Tests for app.core.config."""

import os
from unittest.mock import patch


def test_settings_loads_defaults():
    """Settings should have safe defaults even when no env vars are set."""
    with patch.dict(os.environ, {}, clear=True):
        from app.core.config import load_settings

        settings = load_settings()
        assert settings.azure.endpoint == "https://openai-osaa-v2.openai.azure.com/"
        assert settings.acled.token_url == "https://acleddata.com/oauth/token"
        assert settings.sdg.api_url == "https://unstats.un.org/sdgs/UNSDGAPIV5"


def test_settings_reads_env():
    """Settings should pick up values from environment variables."""
    with patch.dict(os.environ, {"azure": "test-key-123", "acled_email": "a@b.com"}, clear=False):
        from app.core.config import load_settings

        settings = load_settings()
        assert settings.azure.api_key == "test-key-123"
        assert settings.acled.email == "a@b.com"
