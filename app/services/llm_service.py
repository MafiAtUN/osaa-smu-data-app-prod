"""Multi-provider LLM factory supporting Azure OpenAI and Ollama.

All other modules should import ``get_llm`` (provider-agnostic) or
``create_azure_llm`` / ``create_ollama_llm`` (provider-specific) from here.
"""

from __future__ import annotations

import ast
import builtins
import os
from typing import Any

import streamlit as st
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_openai import AzureChatOpenAI, AzureOpenAIEmbeddings

from app.core.config import DEFAULT_LLM, LLM_PROVIDERS, get_settings
from app.core.logging import get_logger

logger = get_logger(__name__)

# ---------------------------------------------------------------------------
# Proxy-environment variable names that must be stripped before creating
# Azure OpenAI clients.
# ---------------------------------------------------------------------------
_PROXY_VARS = [
    "HTTP_PROXY", "HTTPS_PROXY", "http_proxy", "https_proxy",
    "OPENAI_PROXY", "ALL_PROXY", "all_proxy", "NO_PROXY", "no_proxy",
]


def _patch_httpx_and_openai() -> None:
    """Monkey-patch httpx and the AzureOpenAI client to drop ``proxies``."""
    try:
        import httpx
        from openai import AzureOpenAI

        if getattr(httpx.Client.__init__, "_proxy_patched", False):
            return

        original_client_init = httpx.Client.__init__

        def _patched_client_init(self: Any, *args: Any, **kw: Any) -> None:
            kw.pop("proxies", None)
            return original_client_init(self, *args, **kw)

        _patched_client_init._proxy_patched = True  # type: ignore[attr-defined]
        httpx.Client.__init__ = _patched_client_init  # type: ignore[assignment]

        original_async_init = httpx.AsyncClient.__init__

        def _patched_async_init(self: Any, *args: Any, **kw: Any) -> None:
            kw.pop("proxies", None)
            return original_async_init(self, *args, **kw)

        _patched_async_init._proxy_patched = True  # type: ignore[attr-defined]
        httpx.AsyncClient.__init__ = _patched_async_init  # type: ignore[assignment]

        original_openai_init = AzureOpenAI.__init__

        def _patched_openai_init(self: Any, *args: Any, **kw: Any) -> None:
            kw.pop("proxies", None)
            return original_openai_init(self, *args, **kw)

        _patched_openai_init._proxy_patched = True  # type: ignore[attr-defined]
        AzureOpenAI.__init__ = _patched_openai_init  # type: ignore[assignment]
    except Exception:
        logger.debug("Proxy patching skipped — httpx or openai not importable")


_patch_httpx_and_openai()


def _strip_proxy_env() -> dict[str, str | None]:
    """Remove all proxy-related env vars and return saved values."""
    saved: dict[str, str | None] = {}
    for var in _PROXY_VARS:
        saved[var] = os.environ.pop(var, None)
    for key in list(os.environ.keys()):
        if "proxy" in key.lower() and key not in saved:
            saved[key] = os.environ.pop(key, None)
    return saved


def _restore_proxy_env(saved: dict[str, str | None]) -> None:
    for var, value in saved.items():
        if value is not None:
            os.environ[var] = value


# ---------------------------------------------------------------------------
# Azure OpenAI factories
# ---------------------------------------------------------------------------

def create_azure_llm(account: str = "osaa", **kwargs: Any) -> AzureChatOpenAI:
    """Create an ``AzureChatOpenAI`` instance for the given *account*.

    *account* can be ``"osaa"``, ``"osaa_v2"``, ``"unga"``, or ``"unmiss"``.
    """
    kwargs.pop("proxies", None)
    settings = get_settings()
    cfg = settings.get_azure_account(account)

    kwargs.setdefault("api_key", cfg.api_key)
    kwargs.setdefault("azure_endpoint", cfg.endpoint)
    kwargs.setdefault("openai_api_version", cfg.api_version)

    saved = _strip_proxy_env()
    try:
        return AzureChatOpenAI(**kwargs)
    except Exception as first_err:
        if "proxy" not in str(first_err).lower():
            raise
        minimal = {
            "azure_deployment": kwargs.get("azure_deployment"),
            "api_key": kwargs.get("api_key"),
            "azure_endpoint": kwargs.get("azure_endpoint"),
            "openai_api_version": kwargs.get("openai_api_version"),
        }
        minimal = {k: v for k, v in minimal.items() if v is not None}
        for var in _PROXY_VARS:
            os.environ.pop(var, None)
        try:
            return AzureChatOpenAI(**minimal)
        except Exception as second_err:
            _patch_httpx_and_openai()
            try:
                return AzureChatOpenAI(**minimal)
            except Exception as third_err:
                raise LLMCreationError(
                    f"Failed after all retry attempts: {first_err} / {second_err} / {third_err}"
                ) from third_err
    finally:
        _restore_proxy_env(saved)


def create_azure_embeddings(account: str = "osaa_v2", **kwargs: Any) -> AzureOpenAIEmbeddings:
    """Create ``AzureOpenAIEmbeddings`` for the given *account*."""
    kwargs.pop("proxies", None)
    settings = get_settings()
    cfg = settings.get_azure_account(account)

    kwargs.setdefault("model", "smudataembed")
    kwargs.setdefault("api_key", cfg.api_key)
    kwargs.setdefault("azure_endpoint", cfg.endpoint)
    kwargs.setdefault("openai_api_version", cfg.api_version)

    saved = _strip_proxy_env()
    try:
        return AzureOpenAIEmbeddings(**kwargs)
    except Exception as first_err:
        if "proxy" not in str(first_err).lower():
            raise
        minimal = {
            "model": kwargs.get("model"),
            "api_key": kwargs.get("api_key"),
            "azure_endpoint": kwargs.get("azure_endpoint"),
            "openai_api_version": kwargs.get("openai_api_version"),
        }
        minimal = {k: v for k, v in minimal.items() if v is not None}
        for var in _PROXY_VARS:
            os.environ.pop(var, None)
        try:
            return AzureOpenAIEmbeddings(**minimal)
        except Exception as second_err:
            _patch_httpx_and_openai()
            try:
                return AzureOpenAIEmbeddings(**minimal)
            except Exception as third_err:
                raise LLMCreationError(
                    f"Failed after all retry attempts: {first_err} / {second_err} / {third_err}"
                ) from third_err
    finally:
        _restore_proxy_env(saved)


# ---------------------------------------------------------------------------
# Ollama factory
# ---------------------------------------------------------------------------

def create_ollama_llm(model: str = "llama3.3", **kwargs: Any) -> BaseChatModel:
    """Create a ``ChatOllama`` instance for a locally running Ollama model."""
    try:
        from langchain_ollama import ChatOllama
    except ImportError:
        raise LLMCreationError(
            "langchain-ollama is not installed. Run: pip install langchain-ollama"
        )

    settings = get_settings()
    kwargs.setdefault("base_url", settings.ollama.base_url)
    kwargs.setdefault("model", model)
    return ChatOllama(**kwargs)


def get_available_ollama_models() -> list[str]:
    """Query a running Ollama instance for locally available models."""
    try:
        import requests
        settings = get_settings()
        resp = requests.get(f"{settings.ollama.base_url}/api/tags", timeout=3)
        if resp.status_code == 200:
            data = resp.json()
            return sorted(m["name"] for m in data.get("models", []))
    except Exception:
        pass
    return []


# ---------------------------------------------------------------------------
# Provider-agnostic entry point
# ---------------------------------------------------------------------------

def get_selected_llm_name() -> str:
    """Return the name of the currently selected LLM from session state."""
    return st.session_state.get("selected_llm", DEFAULT_LLM)


def get_llm(**kwargs: Any) -> BaseChatModel:
    """Create an LLM instance based on the user's current sidebar selection.

    This is the recommended entry point for all pages and services.
    """
    selected = get_selected_llm_name()

    if selected in LLM_PROVIDERS:
        info = LLM_PROVIDERS[selected]
        return create_azure_llm(
            account=info["account"],
            azure_deployment=info["deployment"],
            **kwargs,
        )

    if selected.startswith("Ollama: "):
        model_name = selected.removeprefix("Ollama: ")
        return create_ollama_llm(model=model_name, **kwargs)

    return create_azure_llm(**kwargs)


# ---------------------------------------------------------------------------
# Code-execution sandbox helpers
# ---------------------------------------------------------------------------

SAFE_BUILTINS: dict[str, Any] = {
    "abs": builtins.abs, "min": builtins.min, "max": builtins.max,
    "sum": builtins.sum, "len": builtins.len, "range": builtins.range,
    "list": builtins.list, "dict": builtins.dict, "set": builtins.set,
    "float": builtins.float, "int": builtins.int, "str": builtins.str,
    "print": builtins.print, "enumerate": builtins.enumerate,
    "zip": builtins.zip,
}

UNSAFE_KEYWORDS: list[str] = [
    "import os", "import subprocess", "import sys", "import importlib",
    "os.", "subprocess.", "sys.", "importlib.",
    "open(", "eval(", "exec(", "__", "shutil", "pathlib",
]

UNSAFE_NAMES: set[str] = {
    "__import__", "breakpoint", "compile", "delattr", "dir", "eval", "exec",
    "getattr", "globals", "help", "input", "locals", "memoryview", "object",
    "open", "setattr", "type", "vars",
}

UNSAFE_CALL_ATTRIBUTES: set[str] = {
    "savefig", "to_clipboard", "to_csv", "to_excel", "to_feather", "to_gbq",
    "to_hdf", "to_html", "to_json", "to_latex", "to_orc", "to_parquet",
    "to_pickle", "to_sql", "to_xml", "write_html", "write_image", "write_json",
}

SAFE_IMPORTS: list[str] = [
    "import pandas", "import numpy", "import plotly", "import matplotlib",
    "import seaborn", "from pandas", "from numpy", "from plotly",
    "from matplotlib", "from seaborn",
]


def validate_code(code: str) -> None:
    """Raise ``ValueError`` if *code* contains unsafe keywords or imports."""
    lowered = code.lower()
    for keyword in UNSAFE_KEYWORDS:
        if keyword in lowered:
            raise ValueError(f"Unsafe keyword detected: {keyword}")

    try:
        tree = ast.parse(code)
    except SyntaxError as exc:
        raise ValueError(f"Invalid Python syntax: {exc.msg}") from exc

    for line in code.splitlines():
        stripped = line.strip().lower()
        if not (stripped.startswith("import ") or (stripped.startswith("from ") and " import " in stripped)):
            continue
        if not any(safe in stripped for safe in SAFE_IMPORTS):
            raise ValueError(f"Unsafe import detected: {stripped}")

    for node in ast.walk(tree):
        if isinstance(node, ast.Name) and node.id in UNSAFE_NAMES:
            raise ValueError(f"Unsafe name detected: {node.id}")
        if isinstance(node, ast.Attribute):
            if node.attr.startswith("_"):
                raise ValueError(f"Unsafe attribute detected: {node.attr}")
            if node.attr in UNSAFE_CALL_ATTRIBUTES:
                raise ValueError(f"Unsafe method detected: {node.attr}")
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id in UNSAFE_NAMES:
            raise ValueError(f"Unsafe call detected: {node.func.id}")


def clean_import_statements(code: str) -> str:
    """Strip import lines from LLM-generated code (modules are pre-injected)."""
    out: list[str] = []
    for line in code.splitlines():
        stripped = line.strip()
        if stripped.startswith("import ") or (stripped.startswith("from ") and " import " in stripped):
            continue
        out.append(line)
    return "\n".join(out)


class LLMCreationError(Exception):
    """Raised when all attempts to create an LLM client fail."""
