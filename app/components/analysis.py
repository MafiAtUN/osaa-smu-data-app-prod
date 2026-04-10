"""LLM-powered data analysis and visualization UI components."""

from __future__ import annotations

import hashlib
import re

import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st
from langchain_core.chat_history import BaseChatMessageHistory, InMemoryChatMessageHistory
from langchain_core.messages import HumanMessage
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.runnables.history import RunnableWithMessageHistory

from app.core.logging import get_logger
from app.services.llm_service import (
    SAFE_BUILTINS,
    clean_import_statements,
    get_llm,
    validate_code,
)

logger = get_logger(__name__)


# ---------------------------------------------------------------------------
# Data summarisation helpers
# ---------------------------------------------------------------------------

def _summarize_dataframe(df: pd.DataFrame) -> str:
    """Generate a detailed textual summary of *df* for the LLM prompt."""
    numeric_cols = df.select_dtypes(include=[np.number]).columns.tolist()
    lines: list[str] = []
    for col in df.columns:
        dtype = df[col].dtype
        if col in numeric_cols:
            non_null = df[col].notna().sum()
            if non_null > 0:
                sample = df[col].dropna().head(3).tolist()
                lines.append(f"- {col}: {dtype} (numeric) - Sample values: {sample}")
            else:
                lines.append(f"- {col}: {dtype} (numeric, all null)")
        else:
            uniq = df[col].nunique()
            sample = df[col].dropna().head(3).tolist() if len(df[col].dropna()) > 0 else []
            lines.append(f"- {col}: {dtype} (categorical/text) - {uniq} unique values - Sample: {sample}")

    first_five = df.head(5).to_string(index=False)
    numeric_list = ", ".join(numeric_cols) if numeric_cols else "None"
    categorical_list = ", ".join(c for c in df.columns if c not in numeric_cols) if df.columns.tolist() else "None"
    return (
        f"This dataset contains {df.shape[0]} rows and {df.shape[1]} columns.\n\n"
        f"NUMERIC COLUMNS: {numeric_list}\n"
        f"CATEGORICAL/TEXT COLUMNS: {categorical_list}\n\n"
        f"Detailed column information:\n" + "\n".join(lines) +
        f"\n\nFirst 5 rows:\n{first_five}"
    )


def _summarize_dataframe_short(df: pd.DataFrame) -> str:
    """Shorter summary for graph-generation prompts."""
    col_info = "\n".join(f"- {col}: {dtype}" for col, dtype in zip(df.columns, df.dtypes))
    first_five = df.head(5).to_string(index=False)
    return (
        f"This dataset contains {df.shape[0]} rows and {df.shape[1]} columns.\n"
        f"Columns:\n{col_info}\n\nFirst 5 rows:\n{first_five}"
    )


def _df_hash(df: pd.DataFrame) -> str:
    """Return a short stable hash of a DataFrame's shape + columns."""
    key = f"{df.shape[0]}x{df.shape[1]}_{'|'.join(sorted(df.columns.tolist()))}"
    return hashlib.md5(key.encode()).hexdigest()[:12]


# ---------------------------------------------------------------------------
# Code execution helpers
# ---------------------------------------------------------------------------

def _run_code(code: str, df: pd.DataFrame) -> object:
    """Execute sanitised *code* and return the ``output`` variable."""
    cleaned = clean_import_statements(code)
    validate_code(cleaned)
    local_vars = {"df": df, "pd": pd, "np": np}
    exec(cleaned, {"__builtins__": SAFE_BUILTINS}, local_vars)
    return local_vars["output"]


def _run_fig_code(code: str, df: pd.DataFrame) -> object:
    """Execute sanitised *code* and return the ``fig`` variable."""
    cleaned = clean_import_statements(code)
    validate_code(cleaned)
    local_vars = {"df": df, "pd": pd, "np": np, "go": go, "px": px}
    exec(cleaned, {"__builtins__": SAFE_BUILTINS}, local_vars)
    return local_vars["fig"]


# ---------------------------------------------------------------------------
# Output rendering helper
# ---------------------------------------------------------------------------

def _render_output(output: object) -> None:
    """Render any type of analysis output inside the current chat message."""
    if isinstance(output, pd.DataFrame):
        st.dataframe(output, use_container_width=True)
    elif isinstance(output, pd.Series):
        st.dataframe(output.to_frame().reset_index(), use_container_width=True)
    elif isinstance(output, dict):
        if output and all(isinstance(v, (pd.DataFrame, pd.Series)) for v in output.values()):
            for key, val in output.items():
                st.markdown(f"**{key.replace('_', ' ').title()}**")
                if isinstance(val, pd.Series):
                    st.dataframe(val.to_frame().reset_index(), use_container_width=True)
                else:
                    st.dataframe(val, use_container_width=True)
        else:
            try:
                st.dataframe(pd.DataFrame(output), use_container_width=True)
            except Exception:
                st.info(f"**Output:** {output}")
    elif isinstance(output, (list, tuple, np.ndarray)):
        try:
            st.dataframe(
                pd.DataFrame(output if not isinstance(output, np.ndarray) else output),
                use_container_width=True,
            )
        except Exception:
            st.info(f"**Output:** {output}")
    elif isinstance(output, Exception):
        st.error(f"An error occurred: {output}")
    else:
        st.info(f"**Output:** {output}")


# ---------------------------------------------------------------------------
# Dataset context auto-analysis
# ---------------------------------------------------------------------------

_CONTEXT_PROMPT = """\
You are a data analyst. Based on the dataset summary below, produce a concise dataset profile.
Structure your response with these sections (use markdown):

**What this dataset contains** — 1-2 sentences describing the subject matter.

**Key columns** — brief description of the most important 3-6 columns and what they represent.

**Quick observations** — 3-5 bullet points about patterns, value ranges, or notable features.

**Data quality notes** — flag any missing values, outliers, or data issues worth knowing.

**Suggested analysis directions** — 2-3 concrete analysis ideas that make sense for this data.

Be concise and practical. Do not invent facts not supported by the summary.

Dataset summary:
{summary}
"""


def _generate_context_summary(df: pd.DataFrame) -> str:
    """Single-shot LLM call to profile the dataset. Returns markdown string."""
    llm = get_llm()
    summary = _summarize_dataframe(df)
    response = llm.invoke([HumanMessage(content=_CONTEXT_PROMPT.format(summary=summary))])
    return response.content


def _render_dataset_context(df: pd.DataFrame) -> None:
    """Display a cached auto-generated dataset profile in an expander."""
    ctx_key = f"_ctx_{_df_hash(df)}"
    if ctx_key not in st.session_state:
        with st.spinner("Analyzing dataset context…"):
            try:
                st.session_state[ctx_key] = _generate_context_summary(df)
            except Exception as exc:
                st.session_state[ctx_key] = f"*Could not generate context: {exc}*"
    with st.expander("📋 Dataset Understanding", expanded=True):
        st.markdown(st.session_state[ctx_key])


# ---------------------------------------------------------------------------
# System prompts
# ---------------------------------------------------------------------------

_ANALYSIS_SYSTEM_PROMPT = (
    "You are an expert data analyst specializing in comprehensive, insightful data analysis. "
    "Your goal is to provide detailed analysis that goes beyond basic statistics.\n\n"
    "TABULAR OUTPUT REQUIREMENTS:\n"
    "- ALWAYS use DataFrames for displaying results when possible.\n"
    "- Store your answer in a variable called 'output'.\n\n"
    "CODE REQUIREMENTS:\n"
    "- Use Pandas. Do NOT create visualizations.\n"
    "- The data is in a DataFrame variable called 'df'.\n"
    "- ONLY aggregate NUMERIC columns.\n"
    "- 'output' should be a Pandas DataFrame whenever possible.\n\n"
    "RESPONSE FORMAT:\n"
    "1. EXPLANATION  2. KEY FINDINGS  3. DETAILED ANALYSIS  4. CONTEXT  5. CODE"
)

_VIZ_SYSTEM_PROMPT = """\
You are a senior data visualization engineer. Before writing any code you MUST reason step-by-step:

STEP 1 — UNDERSTAND THE DATA
Examine the dataset summary carefully. Identify column types (numeric vs categorical), cardinality \
(number of unique values), value ranges, and whether time is involved.

STEP 2 — CHOOSE THE RIGHT CHART
Pick the most appropriate chart type for the question:
  • Compare values across categories (≤8 cats): vertical bar chart
  • Compare values across categories (>8 cats or long names): horizontal bar chart
  • Trend over time / continuous x-axis: line chart
  • Distribution of a single numeric column: histogram
  • Spread and outliers across groups: box plot
  • Relationship between two numeric columns: scatter plot
  • Part-of-whole composition (≤6 categories only): donut chart
  • Two categorical dimensions + numeric value: heatmap
  • Geographic data with country/ISO codes: choropleth map

STEP 3 — PREPARE THE DATA
Aggregate, sort, and clean BEFORE plotting. Never pass raw un-aggregated rows to a summary chart. \
Drop NaN values in columns used for axes/color. Convert date strings to datetime if needed. \
Limit to the top N (e.g. top 15) when cardinality is very high.

STEP 4 — WRITE THE CODE
Follow ALL rules below without exception.

━━━ CODE RULES ━━━
- Use ONLY Plotly (px or go), Pandas, and NumPy. NO import statements.
- The DataFrame is available as 'df'. Store the final figure in a variable called 'fig'.
- NEVER call fig.show() or print().

━━━ ANTI-OVERLAP RULES (CRITICAL) ━━━
- X-axis tick labels: ALWAYS set xaxis_tickangle=-45 when there are more than 5 categories.
- For more than 12 categories on x-axis: switch to a HORIZONTAL bar chart (x=value, y=category).
- Bar text labels: use textposition='outside' and add bottom margin ≥ 80.
- Long category names (>12 chars): use horizontal bar chart so labels have room.
- Legends: if more than 6 items, move legend outside → legend=dict(orientation='v', x=1.02, y=1).
- Annotations: never stack two annotations at the same position; offset them or omit entirely.
- Always set enough margins: fig.update_layout(margin=dict(l=100, r=40, t=90, b=110)).
- For scatter plots with many points: use opacity=0.6 and marker size ≤ 8.

━━━ STYLING RULES ━━━
- Color sequence: ['#2563EB','#7C3AED','#059669','#DC2626','#D97706','#0891B2','#DB2777','#65A30D']
- Title: fig.update_layout(title_text='Descriptive Title Here', title_font=dict(size=18, family='Inter, Arial, sans-serif'))
- Axis labels: always set xaxis_title and yaxis_title with font size 13.
- Background: fig.update_layout(plot_bgcolor='white', paper_bgcolor='white')
- Gridlines: keep only on the value axis with color='#E5E7EB', gridwidth=1. Remove from category axis.
- Hover: include meaningful hover_data or hovertemplate — never show raw index numbers.
- For bar charts: use bargap=0.3 and a subtle bar border: marker_line_color='rgba(0,0,0,0.1)', marker_line_width=0.8
"""

_VIZ_CHART_TYPES: list[tuple[str, str]] = [
    ("Bar Chart", "bar chart showing "),
    ("Horiz. Bar", "horizontal bar chart showing "),
    ("Line Chart", "line chart showing trends in "),
    ("Scatter Plot", "scatter plot comparing "),
    ("Histogram", "histogram of the distribution of "),
    ("Box Plot", "box plot showing spread of "),
    ("Donut Chart", "donut chart of the composition of "),
    ("Heatmap", "heatmap of "),
]


# ---------------------------------------------------------------------------
# Internal chat renderer
# ---------------------------------------------------------------------------

_SUGG_PLACEHOLDER = "— Select a suggestion to pre-fill the prompt —"


def _render_analysis_chat(
    df: pd.DataFrame,
    chat_session_id: str,
    page: str,
    dataset_name: str,
    suggestions: list[str] | None,
) -> None:
    """Render the suggestions dropdown + conversational chat with DuckDB persistence."""
    from app.services.chat_history_service import create_session, save_message

    # ── Suggestions dropdown ──────────────────────────────────────────────
    if suggestions:
        chosen = st.selectbox(
            "Suggestions",
            [_SUGG_PLACEHOLDER] + suggestions,
            key=f"{chat_session_id}_sugg_sel",
            label_visibility="collapsed",
        )
        if chosen != _SUGG_PLACEHOLDER:
            if st.button("↑ Use this suggestion", key=f"{chat_session_id}_sugg_btn"):
                st.session_state[f"{chat_session_id}_prefill"] = chosen
                st.rerun()

    # ── LangChain in-memory history ───────────────────────────────────────
    if "_lc_hist" not in st.session_state:
        st.session_state["_lc_hist"] = {}

    def _get_history(session_id: str) -> BaseChatMessageHistory:
        if session_id not in st.session_state["_lc_hist"]:
            st.session_state["_lc_hist"][session_id] = InMemoryChatMessageHistory()
        return st.session_state["_lc_hist"][session_id]

    prompt = ChatPromptTemplate.from_messages([
        ("system", _ANALYSIS_SYSTEM_PROMPT),
        MessagesPlaceholder(variable_name="messages"),
        ("system", "DATASET SUMMARY: {data_summary}."),
    ])
    llm = get_llm()
    chain = prompt | llm
    chain_with_history = RunnableWithMessageHistory(chain, _get_history, input_messages_key="messages")

    # ── Render existing chat messages ─────────────────────────────────────
    messages_container = st.container()
    with messages_container:
        existing = _get_history(chat_session_id)
        for msg in existing.messages:
            st.chat_message(msg.type).write(msg.content)

    # ── Process pending question ──────────────────────────────────────────
    prompt_key = f"{chat_session_id}_last_question"
    db_session_key = f"{chat_session_id}_db_sid"

    if prompt_key in st.session_state:
        question = st.session_state.pop(prompt_key)

        with messages_container:
            st.chat_message("human").write(question)

        # Persist to DuckDB — create session on first message
        if db_session_key not in st.session_state:
            db_sid = create_session(page, dataset_name, _df_hash(df), question)
            st.session_state[db_session_key] = db_sid
        save_message(st.session_state[db_session_key], "human", question)

        with st.spinner("Analyzing…"):
            response = chain_with_history.invoke(
                {
                    "messages": [HumanMessage(content=question)],
                    "data_summary": _summarize_dataframe(df),
                },
                config={"configurable": {"session_id": chat_session_id}},
            )

        # Persist assistant response
        save_message(st.session_state[db_session_key], "assistant", response.content)

        # Execute code block if present
        code_match = re.search(r"```(?:[Pp]ython)?(.*?)```", response.content, re.DOTALL)
        output = None
        if code_match:
            code_block = re.sub(r"(?m)^\s*fig\.show\(\)\s*$", "", code_match.group(1).strip())
            try:
                output = _run_code(code_block, df)
            except Exception as exc:
                with messages_container:
                    st.chat_message("assistant").error(f"Code execution error: {exc}")
                    st.code(code_block, language="python")

        with messages_container:
            with st.chat_message("assistant"):
                st.write(response.content)
                if output is not None:
                    _render_output(output)

    # ── Input form ────────────────────────────────────────────────────────
    prefill = st.session_state.pop(f"{chat_session_id}_prefill", "")
    with st.form(key=f"{chat_session_id}_analysis_form", clear_on_submit=True):
        col1, col2 = st.columns([4, 1])
        with col1:
            question = st.text_input(
                "Ask about the data…",
                value=prefill,
                key=f"{chat_session_id}_text_input",
                label_visibility="collapsed",
                placeholder="e.g. What are the top 5 countries by fatalities?",
            )
        with col2:
            submitted = st.form_submit_button("Ask", use_container_width=True, type="primary")
        if submitted and question:
            st.session_state[prompt_key] = question
            st.rerun()


# ---------------------------------------------------------------------------
# Public: unified tabbed component
# ---------------------------------------------------------------------------

def render_analysis_tabs(
    df: pd.DataFrame,
    chat_session_id: str,
    page: str = "generic",
    dataset_name: str = "Dataset",
    suggestions: list[str] | None = None,
) -> None:
    """Render Analysis and Visualization as two switchable tabs.

    Parameters
    ----------
    df:               The active DataFrame.
    chat_session_id:  Unique key scoped to this page's session.
    page:             Short page identifier ("acled", "wb", "sdg", "generic").
    dataset_name:     Human-readable dataset label for the chat library.
    suggestions:      Optional list of pre-generated analysis / viz prompts
                      shown in a compact dropdown inside the Analysis tab.
    """
    tab_analysis, tab_viz = st.tabs(["📊 Analysis", "🎨 Visualizations"])

    with tab_analysis:
        st.info(
            "The AI has profiled this dataset below. Use the suggestions dropdown or the chat "
            "box to explore it. Results are exploratory — always verify before publication.",
            icon="ℹ️",
        )
        _render_dataset_context(df)
        _render_analysis_chat(df, chat_session_id, page, dataset_name, suggestions)

    with tab_viz:
        llm_graph_maker(df)


# ---------------------------------------------------------------------------
# Visualization tool
# ---------------------------------------------------------------------------

def llm_graph_maker(df: pd.DataFrame) -> None:
    """Render the natural-language graph-generation widget."""
    st.info(
        "Describe what you want to visualize. The AI will reason about the best chart type, "
        "prepare the data, and generate clean Plotly code. Results are exploratory — verify before publication.",
        icon="📊",
    )

    # Use a stable hash instead of id(df) — id() changes on every rerun because the
    # DataFrame object is re-created, causing session_state keys to never match.
    dh = _df_hash(df)

    # --- Chart-type quick-select buttons ---
    st.caption("Quick chart type:")
    cols = st.columns(len(_VIZ_CHART_TYPES))
    for col, (label, prefix) in zip(cols, _VIZ_CHART_TYPES):
        if col.button(label, key=f"viz_chip_{label}_{dh}", use_container_width=True):
            st.session_state[f"viz_prefix_{dh}"] = prefix

    prompt_tmpl = ChatPromptTemplate.from_messages([
        ("system", _VIZ_SYSTEM_PROMPT),
        ("system", "DATASET SUMMARY:\n{data_summary}"),
        MessagesPlaceholder(variable_name="messages"),
    ])
    llm = get_llm()
    chain = prompt_tmpl | llm

    viz_container = st.container()
    viz_key = f"viz_last_prompt_{dh}"

    if viz_key in st.session_state:
        graph_prompt = st.session_state.pop(viz_key)
        with viz_container:
            st.chat_message("human").write(graph_prompt)

        with st.spinner("Reasoning about data and generating visualization…"):
            response = chain.invoke({
                "data_summary": _summarize_dataframe_short(df),
                "messages": [HumanMessage(content=graph_prompt)],
            })
            code_match = re.search(r"```(?:[Pp]ython)?(.*?)```", response.content, re.DOTALL)
            fig = None
            if code_match:
                code_block = re.sub(r"(?m)^\s*fig\.show\(\)\s*$", "", code_match.group(1).strip())
                try:
                    fig = _run_fig_code(code_block, df)
                except Exception as exc:
                    with viz_container:
                        st.chat_message("assistant").error(f"Code execution error: {exc}")
                        st.code(code_block, language="python")
            else:
                with viz_container:
                    st.chat_message("assistant").markdown(response.content)

            if fig is not None:
                with viz_container:
                    with st.chat_message("assistant"):
                        st.plotly_chart(fig, use_container_width=True)
                        with st.expander("View generated code"):
                            st.code(code_block, language="python")

    prefix = st.session_state.pop(f"viz_prefix_{dh}", "")
    with st.form(key=f"viz_form_{dh}", clear_on_submit=True):
        col1, col2 = st.columns([4, 1])
        with col1:
            graph_prompt = st.text_input(
                "Describe the visualization…",
                value=prefix,
                key=f"viz_text_{dh}",
                label_visibility="collapsed",
                placeholder="e.g. bar chart of top 10 countries by fatalities",
            )
        with col2:
            submitted = st.form_submit_button("Generate", use_container_width=True, type="primary")
        if submitted and graph_prompt:
            st.session_state[viz_key] = graph_prompt
            st.rerun()
