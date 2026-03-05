"""Sidebar widget for choosing the active LLM provider / model."""

from __future__ import annotations

import streamlit as st

from app.core.config import DEFAULT_LLM, LLM_PROVIDERS, OLLAMA_MODELS
from app.services.llm_service import get_available_ollama_models

_PROVIDER_ICONS = {
    "anthropic": "🟣",
    "xai": "⚡",
    "openai": "🟢",
    "meta": "🦙",
    "moonshot": "🌙",
    "router": "🔀",
    "ollama": "🏠",
}

_PROVIDER_LABELS = {
    "anthropic": "Anthropic (via Azure)",
    "xai": "xAI (via Azure)",
    "meta": "Meta (via Azure)",
    "moonshot": "MoonshotAI (via Azure)",
    "openai": "OpenAI (via Azure)",
    "router": "Azure AI Router",
    "ollama": "Ollama (local)",
}


def _model_category(name: str) -> str:
    lower = name.lower()
    if "claude" in lower:
        return "anthropic"
    if "grok" in lower:
        return "xai"
    if "llama" in lower:
        return "meta"
    if "kimi" in lower:
        return "moonshot"
    if "router" in lower:
        return "router"
    if "ollama" in lower:
        return "ollama"
    return "openai"


def render_llm_selector() -> None:
    """Render the active-model selector directly in the sidebar (no expander)."""

    with st.sidebar:
        # Section header styled via global CSS class
        st.markdown(
            '<span class="smu-llm-header">🤖 Active Model</span>',
            unsafe_allow_html=True,
        )

        # Build the full model list
        azure_options = list(LLM_PROVIDERS.keys())

        ollama_running = False
        local_models: list[str] = []
        try:
            local_models = get_available_ollama_models()
            if local_models:
                ollama_running = True
        except Exception:
            pass

        ollama_options = [f"Ollama: {m}" for m in local_models] if local_models else []
        extra_ollama = [
            f"Ollama: {m}" for m in OLLAMA_MODELS if f"Ollama: {m}" not in ollama_options
        ]
        all_options = azure_options + ollama_options + extra_ollama

        current = st.session_state.get("selected_llm", DEFAULT_LLM)
        if current not in all_options:
            current = DEFAULT_LLM
        idx = all_options.index(current) if current in all_options else 0

        def _format_option(name: str) -> str:
            cat = _model_category(name)
            icon = _PROVIDER_ICONS.get(cat, "")
            return f"{icon} {name}"

        selected = st.selectbox(
            "Model",
            all_options,
            index=idx,
            format_func=_format_option,
            key="_llm_selector_widget",
            help="Choose which language model to use across the app.",
            label_visibility="collapsed",
        )

        st.session_state["selected_llm"] = selected

        # Info card beneath the selector
        info = LLM_PROVIDERS.get(selected)
        if info:
            cat = _model_category(selected)
            provider_label = _PROVIDER_LABELS.get(cat, "Azure AI")
            st.markdown(
                f"""
                <div class="smu-llm-info">
                    <div class="smu-llm-info-row">
                        <span>Provider</span>
                        <span>{provider_label}</span>
                    </div>
                    <div class="smu-llm-info-row">
                        <span>Model</span>
                        <span>{info["model"]}</span>
                    </div>
                    <div class="smu-llm-info-row">
                        <span>Account</span>
                        <span>{info["account"]}</span>
                    </div>
                </div>
                """,
                unsafe_allow_html=True,
            )
        elif selected and selected.startswith("Ollama: "):
            model_name = selected.removeprefix("Ollama: ")
            available = ollama_running and model_name in local_models
            status_icon = "✅" if available else "❌"
            status_text = "Available" if available else "Not running"
            st.markdown(
                f"""
                <div class="smu-llm-info">
                    <div class="smu-llm-info-row">
                        <span>Provider</span>
                        <span>Ollama (local)</span>
                    </div>
                    <div class="smu-llm-info-row">
                        <span>Model</span>
                        <span>{model_name}</span>
                    </div>
                    <div class="smu-llm-info-row">
                        <span>Status</span>
                        <span>{status_icon} {status_text}</span>
                    </div>
                </div>
                """,
                unsafe_allow_html=True,
            )
            if not available:
                st.warning(
                    f"**{model_name}** is not available. Start Ollama and pull the model:\n\n"
                    f"```\nollama pull {model_name}\n```"
                )
