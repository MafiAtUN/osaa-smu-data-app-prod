"""Sidebar widget for choosing the active LLM provider and model.

Renders a persistent sidebar selector that lists all configured LLM providers
(Azure OpenAI accounts and local Ollama) and their available models.  Stores the
user's selection in ``st.session_state`` and displays a provider/model/account
info card.  Key export: ``render_llm_selector``.
"""

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

            # Speed badge colour
            _speed_colors = {
                "Very Fast": "#16A34A",
                "Fast": "#2563EB",
                "Medium": "#D97706",
                "Varies": "#64748B",
            }
            speed = info.get("speed", "")
            speed_color = _speed_colors.get(speed, "#64748B")

            # Tier badge colour
            _tier_colors = {
                "Flagship": "#7C3AED",
                "Efficient": "#2563EB",
                "Lightweight": "#0891B2",
                "Open-source": "#059669",
                "Router": "#64748B",
            }
            tier = info.get("tier", "")
            tier_color = _tier_colors.get(tier, "#64748B")

            description = info.get("description", "")
            context_window = info.get("context_window", "")
            max_output = info.get("max_output", "")
            strengths = info.get("strengths", "")
            params = info.get("params", "")
            modalities: list[str] = info.get("modalities", [])
            knowledge_cutoff = info.get("knowledge_cutoff", "")

            def _badge(label: str, bg: str, fg: str) -> str:
                return (
                    f'<span style="background:{bg};color:{fg};border:1px solid {fg}40;'
                    f'border-radius:4px;padding:1px 6px;font-size:0.6rem;font-weight:600;'
                    f'margin-right:3px;white-space:nowrap;">{label}</span>'
                )

            # Tier + speed badges
            top_badges = ""
            if tier:
                top_badges += _badge(tier, f"{tier_color}1A", tier_color)
            if speed:
                top_badges += _badge(speed, f"{speed_color}1A", speed_color)

            # Modality chips
            _modality_icons = {"Text": "T", "Vision": "👁"}
            modality_html = ""
            for m in modalities:
                icon = _modality_icons.get(m, m)
                modality_html += _badge(f"{icon} {m}", "#1E293B", "#94A3B8")

            def _row(label: str, value: str, value_style: str = "") -> str:
                style = f' style="{value_style}"' if value_style else ""
                return (
                    f'<div class="smu-llm-info-row">'
                    f'<span>{label}</span><span{style}>{value}</span></div>'
                )

            st.markdown(
                f"""
                <div class="smu-llm-info">
                    <div style="font-size:0.68rem;color:#94A3B8;margin-bottom:0.4rem;line-height:1.4;">{description}</div>
                    <div style="margin-bottom:0.4rem;">{top_badges}</div>
                    {f'<div style="margin-bottom:0.6rem;">{modality_html}</div>' if modality_html else ""}
                    {_row("Provider", provider_label)}
                    {_row("Model", info["model"])}
                    {_row("Account", info["account"])}
                    {_row("Parameters", params) if params else ""}
                    {_row("Context in", context_window) if context_window else ""}
                    {_row("Max output", max_output) if max_output else ""}
                    {_row("Knowledge", knowledge_cutoff) if knowledge_cutoff else ""}
                    {_row("Strengths", strengths, "text-align:right;max-width:58%;font-size:0.65rem;") if strengths else ""}
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
