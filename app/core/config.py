"""Centralized configuration loaded from environment variables and Streamlit secrets."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Optional

import streamlit as st


def _get(key: str, default: Optional[str] = None) -> Optional[str]:
    """Read a value from Streamlit secrets first, then environment variables."""
    try:
        return st.secrets[key]
    except (KeyError, FileNotFoundError, AttributeError):
        return os.getenv(key, default)


# ---------------------------------------------------------------------------
# Azure AI account configs
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class AzureAccountConfig:
    api_key: str = ""
    endpoint: str = ""
    api_version: str = "2024-05-01-preview"


# ---------------------------------------------------------------------------
# Ollama (local LLMs)
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class OllamaConfig:
    base_url: str = "http://localhost:11434"


# ---------------------------------------------------------------------------
# LLM model registry — each entry is a user-facing option
# ---------------------------------------------------------------------------

LLM_PROVIDERS: dict[str, dict] = {
    # ---- xAI Grok (via Azure UNMISS) ----
    "Grok 3 Mini": {
        "provider": "azure",
        "account": "unmiss",
        "deployment": "grok-3-mini",
        "model": "grok-3-mini",
        "description": "xAI Grok 3 Mini — fast reasoning model",
    },
    # ---- OpenAI GPT-5.x (via Azure UNMISS) ----
    "GPT-5.2": {
        "provider": "azure",
        "account": "unmiss",
        "deployment": "gpt-5.2-chat",
        "model": "gpt-5.2-chat",
        "description": "OpenAI GPT-5.2 — latest flagship model",
    },
    # ---- OpenAI GPT-5 (via Azure UNGA) ----
    "GPT-5 (UNGA)": {
        "provider": "azure",
        "account": "unga",
        "deployment": "gpt-5-unga",
        "model": "gpt-5",
        "description": "OpenAI GPT-5 via UNGA account",
    },
    # ---- OpenAI GPT-5 (via Azure OSAA v2) ----
    "GPT-5 (OSAA)": {
        "provider": "azure",
        "account": "osaa_v2",
        "deployment": "gpt-5-osaa",
        "model": "gpt-5",
        "description": "OpenAI GPT-5 via OSAA v2 account",
    },
    # ---- OpenAI GPT-4o (via Azure OSAA) ----
    "GPT-4o (OSAA)": {
        "provider": "azure",
        "account": "osaa",
        "deployment": "OSSAA",
        "model": "gpt-4o",
        "description": "OpenAI GPT-4o via OSAA account",
    },
    # ---- OpenAI GPT-4o (via Azure UNGA) ----
    "GPT-4o (UNGA)": {
        "provider": "azure",
        "account": "unga",
        "deployment": "gpt-4o-unga",
        "model": "gpt-4o",
        "description": "OpenAI GPT-4o via UNGA account",
    },
    # ---- OpenAI GPT-4.1 (via Azure UNMISS) ----
    "GPT-4.1": {
        "provider": "azure",
        "account": "unmiss",
        "deployment": "gpt-4.1",
        "model": "gpt-4.1",
        "description": "OpenAI GPT-4.1 — strong general-purpose model",
    },
    # ---- OpenAI GPT-4.1-mini (via Azure OSAA) ----
    "GPT-4.1-mini (OSAA)": {
        "provider": "azure",
        "account": "osaa",
        "deployment": "OSAA",
        "model": "gpt-4.1-mini",
        "description": "OpenAI GPT-4.1-mini — fast & affordable",
    },
    # ---- OpenAI GPT-4.1-mini (via Azure UNMISS) ----
    "GPT-4.1-mini (UNMISS)": {
        "provider": "azure",
        "account": "unmiss",
        "deployment": "gpt-4.1-mini",
        "model": "gpt-4.1-mini",
        "description": "OpenAI GPT-4.1-mini — fast & affordable",
    },
    # ---- OpenAI GPT-4o-mini (via Azure OSAA v2) ----
    "GPT-4o-mini": {
        "provider": "azure",
        "account": "osaa_v2",
        "deployment": "osaa_app",
        "model": "gpt-4o-mini",
        "description": "OpenAI GPT-4o-mini — lightest OpenAI model",
    },
    # ---- Meta Llama (via Azure UNMISS) ----
    "Llama 4 Maverick": {
        "provider": "azure",
        "account": "unmiss",
        "deployment": "Llama-4-Maverick-17B-128E-Instruct-FP8",
        "model": "Llama-4-Maverick-17B-128E-Instruct-FP8",
        "description": "Meta Llama 4 Maverick 17B — open-source powerhouse",
    },
    # ---- MoonshotAI Kimi (via Azure UNMISS) ----
    "Kimi K2.5": {
        "provider": "azure",
        "account": "unmiss",
        "deployment": "Kimi-K2.5",
        "model": "Kimi-K2.5",
        "description": "MoonshotAI Kimi K2.5 — multilingual reasoning model",
    },
    # ---- Model Routers ----
    "Model Router (UNMISS)": {
        "provider": "azure",
        "account": "unmiss",
        "deployment": "model-router",
        "model": "model-router",
        "description": "Azure AI Model Router — auto-selects the best model",
    },
    "Model Router (UNGA)": {
        "provider": "azure",
        "account": "unga",
        "deployment": "model-router",
        "model": "model-router",
        "description": "Azure AI Model Router — auto-selects the best model",
    },
}

OLLAMA_MODELS: list[str] = [
    "llama3.3",
    "llama3.1",
    "mistral",
    "mixtral",
    "phi4",
    "gemma2",
    "qwen2.5",
    "deepseek-r1",
    "command-r",
]

DEFAULT_LLM = "GPT-4o (OSAA)"

# ---------------------------------------------------------------------------
# Other service configs
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class ACLEDConfig:
    email: str = ""
    key: str = ""
    token_url: str = "https://acleddata.com/oauth/token"
    api_url: str = "https://acleddata.com/api/acled/read"


@dataclass(frozen=True)
class SDGConfig:
    api_url: str = "https://unstats.un.org/sdgs/UNSDGAPIV5"


@dataclass(frozen=True)
class AppConfig:
    password: str = ""
    pid_password: str = ""


@dataclass(frozen=True)
class Settings:
    azure_accounts: dict[str, AzureAccountConfig] = field(default_factory=dict)
    ollama: OllamaConfig = field(default_factory=OllamaConfig)
    acled: ACLEDConfig = field(default_factory=ACLEDConfig)
    sdg: SDGConfig = field(default_factory=SDGConfig)
    app: AppConfig = field(default_factory=AppConfig)

    def get_azure_account(self, name: str) -> AzureAccountConfig:
        return self.azure_accounts.get(name, AzureAccountConfig())


def load_settings() -> Settings:
    """Build a *Settings* instance from the current environment / secrets."""
    api_version = _get("AZURE_OPENAI_API_VERSION", "2024-05-01-preview")

    azure_accounts = {
        "osaa": AzureAccountConfig(
            api_key=_get("azure", ""),
            endpoint=_get("AZURE_OPENAI_ENDPOINT", "https://openai-osaa.openai.azure.com/"),
            api_version=api_version,
        ),
        "osaa_v2": AzureAccountConfig(
            api_key=_get("AZURE_OPENAI_V2_KEY", "") or _get("azure", ""),
            endpoint=_get("AZURE_OPENAI_V2_ENDPOINT", "https://openai-osaa-v2.cognitiveservices.azure.com/"),
            api_version=api_version,
        ),
        "unga": AzureAccountConfig(
            api_key=_get("AZURE_OPENAI_UNGA_KEY", ""),
            endpoint=_get("AZURE_OPENAI_UNGA_ENDPOINT", "https://unga-analysis.openai.azure.com/"),
            api_version=api_version,
        ),
        "unmiss": AzureAccountConfig(
            api_key=_get("AZURE_UNMISS_KEY", ""),
            endpoint=_get("AZURE_UNMISS_ENDPOINT", "https://unmiss.cognitiveservices.azure.com/"),
            api_version=api_version,
        ),
    }

    return Settings(
        azure_accounts=azure_accounts,
        ollama=OllamaConfig(
            base_url=_get("OLLAMA_BASE_URL", "http://localhost:11434"),
        ),
        acled=ACLEDConfig(
            email=_get("acled_email", ""),
            key=_get("acled_key", ""),
            token_url=_get("ACLED_TOKEN_URL", "https://acleddata.com/oauth/token"),
            api_url=_get("ACLED_API_URL", "https://acleddata.com/api/acled/read"),
        ),
        sdg=SDGConfig(
            api_url=_get("UN_SDG_API_URL", "https://unstats.un.org/sdgs/UNSDGAPIV5"),
        ),
        app=AppConfig(
            password=_get("app_password", ""),
            pid_password=_get("pid_password", ""),
        ),
    )


def get_settings() -> Settings:
    """Return a cached *Settings* singleton stored in ``st.session_state``."""
    if "_settings" not in st.session_state:
        st.session_state._settings = load_settings()
    return st.session_state._settings
