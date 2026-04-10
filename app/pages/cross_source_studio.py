"""Cross-Source Studio — one natural-language query fetches and combines multiple API datasets.

Orchestrates the full cross-source pipeline: the LLM planner (``cross_source.planner``)
interprets the user's question, the execution engine (``cross_source.execution``) fetches
data from World Bank, ACLED, UN SDG, and other sources in parallel, and the results are
merged, quality-scored (``cross_source.quality``), and displayed with AI analysis via
``render_analysis_tabs``.  Supports scenario saving and Excel export.
"""

from __future__ import annotations

import json
from copy import deepcopy
from datetime import date
from io import BytesIO

import pandas as pd
import plotly.express as px
import streamlit as st
import streamlit.components.v1 as components
from langchain_core.messages import HumanMessage, SystemMessage

from app.components.analysis import render_analysis_tabs
from app.components.styles import page_header, section_divider
from app.services.cross_source import (
    execute_plan,
    init_storage,
    parse_query_plan,
)
from app.services.llm_service import get_llm

page_header(
    "🔗",
    "Cross-Source Studio",
    "Ask one question across multiple APIs (World Bank, ACLED, SDG, UIS, UN Data), auto-fetch and join by country + year.",
    badge="Beta",
)

_prefix = st.session_state.get("_page_prefix", "pages/")
_nav_left, _nav_right = st.columns([6, 1])
with _nav_right:
    st.page_link(
        f"{_prefix}cross_source_sync.py",
        label="Hybrid Sync",
        icon="🗄️",
        use_container_width=True,
    )

init_storage()
components.html(
    """
    <script>
      const scrollRoot = window.parent || window;
      scrollRoot.scrollTo({ top: 0, behavior: "auto" });
    </script>
    """,
    height=0,
)

if "xsrc_last_result" not in st.session_state:
    st.session_state["xsrc_last_result"] = None
if "xsrc_draft_plan" not in st.session_state:
    st.session_state["xsrc_draft_plan"] = None
if "xsrc_assistant_chat" not in st.session_state:
    st.session_state["xsrc_assistant_chat"] = []

SCENARIO_DEMOS = [
    {
        "name": "Country: Algeria GDP vs Population",
        "query": (
            "For Algeria from 2000 to 2024, compare NY.GDP.MKTP.CD (GDP current US$) and "
            "SP.POP.TOTL (population total), then analyze trend and correlation."
        ),
        "purpose": "Build a macro baseline for long-horizon country growth context.",
    },
    {
        "name": "Country: Kenya Electricity vs GDP per Capita",
        "query": (
            "For Kenya from 2000 to 2024, compare EG.ELC.ACCS.ZS (access to electricity %) and "
            "NY.GDP.PCAP.CD (GDP per capita), and assess co-movement."
        ),
        "purpose": "Assess infrastructure and income dynamics for development planning.",
    },
    {
        "name": "All Regions: Electricity Access vs GDP per Capita",
        "query": (
            "From 2000 to 2024, compare EG.ELC.ACCS.ZS (access to electricity %) and "
            "NY.GDP.PCAP.CD (GDP per capita current US$) for all regions, and analyze trend and correlation."
        ),
        "purpose": "Benchmark regional infrastructure and income dynamics with broad coverage.",
    },
    {
        "name": "All Regions: GDP per Capita Trend",
        "query": (
            "From 2000 to 2024, show NY.GDP.PCAP.CD (GDP per capita current US$) trend for all regions."
        ),
        "purpose": "Provide an overview of long-run regional income trend patterns.",
    },
    {
        "name": "Sub-region: Sub-Saharan Africa Electricity vs GDP per Capita",
        "query": (
            "For sub-region Sub-Saharan Africa from 2000 to 2024, compare EG.ELC.ACCS.ZS "
            "(access to electricity %) and NY.GDP.PCAP.CD (GDP per capita current US$)."
        ),
        "purpose": "Study broad sub-regional structural development patterns.",
    },
    {
        "name": "Sub-region: Sub-Saharan Africa GDP vs Electricity Access",
        "query": (
            "For sub-region Sub-Saharan Africa from 2000 to 2024, compare NY.GDP.MKTP.CD "
            "(GDP current US$) and EG.ELC.ACCS.ZS (access to electricity %)."
        ),
        "purpose": "Assess whether aggregate output and infrastructure access move together.",
    },
]

section_divider("How to Use")
st.markdown(
    """
1. Enter a plain-English cross-source question (or load a demo scenario).
2. Optionally add the analysis purpose so the planner can choose better indicators.
3. Click **Fetch + Build Dataset**.
4. Review warnings, coverage diagnostics, and suggestions if data is sparse.
5. Use **Revise Query** actions to improve overlap/coverage, then download final dataset.
"""
)


def _execute_and_store(plan, query_text: str, force_refresh: bool) -> None:
    """Execute a plan and store it in session state as the latest result."""
    result = execute_plan(plan, force_refresh=force_refresh)
    st.session_state["xsrc_last_result"] = {
        "plan": plan,
        "result": result,
        "query": query_text,
    }
    st.session_state["xsrc_draft_plan"] = None


def _build_smart_suggestions(df: pd.DataFrame, plan) -> list[str]:
    """Create richer, dataset-aware analysis suggestions."""
    if df is None or df.empty:
        return []

    metric_cols = [
        c for c in df.columns
        if c not in ("iso3", "country", "year") and pd.api.types.is_numeric_dtype(df[c])
    ]
    if not metric_cols:
        return [
            "Summarize data availability, missingness, and what analyses are still feasible.",
            "Recommend alternative indicators with stronger coverage for this country and period.",
        ]

    m1 = metric_cols[0]
    m2 = metric_cols[1] if len(metric_cols) > 1 else metric_cols[0]
    years_min = int(df["year"].min()) if "year" in df.columns and not df["year"].isna().all() else plan.from_year
    years_max = int(df["year"].max()) if "year" in df.columns and not df["year"].isna().all() else plan.to_year
    has_group = "geo_group" in df.columns

    suggestions = [
        f"Compute Pearson and Spearman correlation between {m1} and {m2}, with confidence caveats on sample size.",
        f"Run a lag analysis: test whether {m1} leads {m2} by 1–3 years.",
        f"Create year-over-year growth rates for {m1} and {m2} and compare turning points.",
        f"Normalize {m1} and {m2} to index=100 in {years_min} and compare trajectories through {years_max}.",
        f"Identify structural breaks and outlier years in {m1} and {m2}.",
        "Quantify overlap coverage by year and explain which years drive the correlation result.",
        f"Fit a simple regression ({m2} ~ {m1}) and interpret sign, fit quality, and limitations.",
        "Test robustness by excluding top 1–2 outlier years and recomputing correlation.",
        "Assess missing-data bias risk and propose whether interpolation is acceptable.",
        "Recommend proxy indicators if current series are too sparse for strong inference.",
        "Summarize policy-relevant findings in 5 bullet points for a non-technical audience.",
        "Draft a short caution note highlighting what cannot be concluded from this dataset.",
    ]
    if has_group:
        suggestions.insert(0, f"Rank geo groups by average {m1} between {years_min} and {years_max}.")
        suggestions.insert(1, f"Identify which geo groups have the fastest growth in {m1}.")
    return suggestions[:12]


section_divider("Cross-Source Query")

st.caption("Quick demo scenarios")
demo_col1, demo_col2 = st.columns([3, 1])
with demo_col1:
    demo_name = st.selectbox(
        "Scenario",
        [d["name"] for d in SCENARIO_DEMOS],
        key="xsrc_demo_name",
        label_visibility="collapsed",
    )
with demo_col2:
    if st.button("Load Scenario", use_container_width=True, key="xsrc_load_demo"):
        chosen = next(d for d in SCENARIO_DEMOS if d["name"] == demo_name)
        st.session_state["xsrc_query"] = chosen["query"]
        st.session_state["xsrc_purpose"] = chosen["purpose"]
        st.rerun()

query = st.text_area(
    "Query",
    key="xsrc_query",
    height=100,
    placeholder=(
        "Example: For Algeria, compare conflict events and GDP over time from 2005 to 2024 "
        "and show if they are correlated."
    ),
    label_visibility="collapsed",
)
analysis_purpose = st.text_input(
    "Analysis purpose (optional)",
    key="xsrc_purpose",
    placeholder="e.g., policy brief, donor report, early-warning monitoring",
)

col1, col2 = st.columns([1, 1])
with col1:
    run_clicked = st.button("Fetch + Build Dataset", type="primary", use_container_width=True)
with col2:
    force_refresh = st.toggle("Force refresh (skip cache)", value=False)

if run_clicked and query.strip():
    with st.spinner("Planning query..."):
        plan = parse_query_plan(query, purpose=analysis_purpose or None)
    st.session_state["xsrc_draft_plan"] = plan
    st.session_state["xsrc_last_query"] = query
    if plan.confidence >= 0.60:
        with st.spinner("Executing plan..."):
            _execute_and_store(plan, query, force_refresh=force_refresh)

draft_plan = st.session_state.get("xsrc_draft_plan")
if draft_plan is not None and draft_plan.confidence < 0.60:
    section_divider("Plan Review Required")
    st.warning(
        f"Planner confidence is low ({draft_plan.confidence:.2f}). "
        "Review and run manually, or refine your query for better precision."
    )
    st.markdown(f"**Country:** {draft_plan.country} (`{draft_plan.country_iso3}`)")
    st.markdown(f"**Years:** {draft_plan.from_year} to {draft_plan.to_year}")
    st.markdown("**Metrics:**")
    for m in draft_plan.metrics:
        st.markdown(f"- `{m.source}` · `{m.series_id}` · {m.label}")

    col_run, col_cancel = st.columns(2)
    with col_run:
        if st.button("Run This Plan Anyway", type="primary", use_container_width=True, key="xsrc_run_draft"):
            with st.spinner("Executing reviewed plan..."):
                _execute_and_store(
                    draft_plan,
                    st.session_state.get("xsrc_last_query", query),
                    force_refresh=force_refresh,
                )
            st.rerun()
    with col_cancel:
        if st.button("Discard Draft Plan", use_container_width=True, key="xsrc_discard_draft"):
            st.session_state["xsrc_draft_plan"] = None
            st.rerun()

payload = st.session_state.get("xsrc_last_result")

if payload:
    plan = payload["plan"]
    result = payload["result"]
    merged_df: pd.DataFrame = result.merged_df

    with st.expander("Execution Plan & Data Sources", expanded=False):
        st.markdown(f"**Country:** {plan.country} (`{plan.country_iso3}`)")
        st.markdown(f"**Scope:** {plan.scope_type} · {plan.scope_name or plan.country}")
        st.markdown(f"**Years:** {plan.from_year} to {plan.to_year}")
        st.markdown(f"**Explanation:** {plan.explanation}")
        st.markdown(f"**Planner confidence:** {plan.confidence:.2f}")
        if plan.purpose:
            st.markdown(f"**Analysis purpose:** {plan.purpose}")
        elif plan.follow_up_questions:
            st.info("Planner needs more context:")
            for q in plan.follow_up_questions:
                st.markdown(f"- {q}")
        st.markdown("**Metrics:**")
        for m in plan.metrics:
            st.markdown(f"- `{m.source}` · `{m.series_id}` · {m.label}")

        st.markdown("**Data Sources Used**")
        source_name_map = {
            "world_bank": "World Bank API (wbgapi)",
            "acled": "ACLED API (OAuth REST)",
            "sdg": "UN SDG API",
            "uis": "UNESCO UIS via data.un.org SDMX",
            "un_data": "UN Data NSI SDMX API",
            "un_energy": "UN Energy via data.un.org SDMX",
        }
        source_rows = []
        for m in plan.metrics:
            source_rows.append(
                {
                    "source_key": m.source,
                    "source_name": source_name_map.get(m.source, m.source),
                    "series_id": m.series_id,
                    "series_label": m.label,
                }
            )
        if source_rows:
            st.dataframe(pd.DataFrame(source_rows), use_container_width=True, hide_index=True)

    with st.expander("Metric Selection Trace", expanded=False):
        trace_rows = []
        for m in plan.metrics:
            trace_rows.append(
                {
                    "metric": f"{m.source}:{m.series_id}",
                    "label": m.label,
                    "selection_method": m.selection_method,
                    "selection_reason": m.selection_reason,
                    "candidate_count": len(m.candidates),
                }
            )
        st.dataframe(pd.DataFrame(trace_rows), use_container_width=True, hide_index=True)
        st.caption("Candidate alternatives considered by planner")
        st.code(
            json.dumps(
                {
                    f"{m.source}:{m.series_id}": m.candidates
                    for m in plan.metrics
                    if m.candidates
                },
                indent=2,
            )
        )

    if result.notes:
        st.warning("\n".join(result.notes))

    with st.expander("Cache Diagnostics", expanded=False):
        if result.cache_diagnostics:
            diag_rows = []
            for metric_key, diag in result.cache_diagnostics.items():
                fetched_ranges = diag.get("fetched_ranges", [])
                fetched_years = diag.get("fetched_years", [])
                diag_rows.append(
                    {
                        "metric": metric_key,
                        "force_refresh": diag.get("force_refresh", False),
                        "cache_hit_years": diag.get("cache_hit_years", 0),
                        "fetched_year_count": len(fetched_years),
                        "fetched_ranges": ", ".join(f"{a}-{b}" for a, b in fetched_ranges) if fetched_ranges else "none",
                        "error": diag.get("error", ""),
                    }
                )
            st.dataframe(pd.DataFrame(diag_rows), use_container_width=True, hide_index=True)
        else:
            st.caption("No cache diagnostics available.")

    with st.expander("Data Coverage & Quality", expanded=False):
        if result.data_diagnostics:
            st.dataframe(pd.DataFrame(result.data_diagnostics), use_container_width=True, hide_index=True)
        else:
            st.caption("No data diagnostics available.")

    if result.guidance:
        st.warning("Advisory:\n" + "\n".join(f"- {g}" for g in result.guidance))

    section_divider("Merged Dataset")
    if merged_df.empty:
        st.info("No rows were returned after execution/joining.")
    else:
        st.caption(f"Result key: `{result.result_key}`")
        st.caption(f"{len(merged_df):,} rows · {len(merged_df.columns)} columns")
        parquet_bytes = None
        try:
            buf = BytesIO()
            merged_df.to_parquet(buf, index=False)
            parquet_bytes = buf.getvalue()
        except Exception:
            parquet_bytes = None

        dl_col1, dl_col2 = st.columns(2)
        with dl_col1:
            st.download_button(
                "Download CSV",
                data=merged_df.to_csv(index=False).encode("utf-8"),
                file_name="cross_source_dataset.csv",
                mime="text/csv",
                use_container_width=True,
                key="xsrc_download_csv",
            )
        with dl_col2:
            if parquet_bytes is not None:
                st.download_button(
                    "Download Parquet",
                    data=parquet_bytes,
                    file_name="cross_source_dataset.parquet",
                    mime="application/octet-stream",
                    use_container_width=True,
                    key="xsrc_download_parquet",
                )
            else:
                st.caption("Parquet export unavailable (missing parquet engine).")
        st.dataframe(merged_df, use_container_width=True)

        section_divider("Revise Query")
        st.caption("One-click refinements based on current data coverage diagnostics.")

        cur_year = date.today().year
        rev_col1, rev_col2, rev_col3 = st.columns(3)
        with rev_col1:
            if plan.to_year > cur_year:
                if st.button("Trim End Year to Current Year", use_container_width=True, key="xsrc_revise_trim_year"):
                    revised = deepcopy(plan)
                    revised.to_year = cur_year
                    if revised.from_year > revised.to_year:
                        revised.from_year = max(revised.to_year - 5, 1960)
                    with st.spinner("Re-running with revised date range..."):
                        _execute_and_store(
                            revised,
                            f"{payload.get('query', '')} (revised: end year {cur_year})",
                            force_refresh=False,
                        )
                    st.rerun()
            if st.button("Widen Date Range by 5 Years", use_container_width=True, key="xsrc_revise_widen"):
                revised = deepcopy(plan)
                revised.from_year = max(plan.from_year - 5, 1960)
                with st.spinner("Re-running with wider date range..."):
                    _execute_and_store(
                        revised,
                        f"{payload.get('query', '')} (revised: widen start year to {revised.from_year})",
                        force_refresh=False,
                    )
                st.rerun()

        sparse_rows = [
            d for d in result.data_diagnostics
            if d.get("status") in {"no_data", "sparse", "insufficient_points"} and d.get("alternatives")
        ]
        with rev_col2:
            if sparse_rows:
                st.caption("Sparse metrics detected. Swap to suggested proxy:")
                for i, d in enumerate(sparse_rows[:3]):
                    metric_key = str(d.get("metric", ""))
                    alt_text = str(d.get("alternatives", ""))
                    first_alt = alt_text.split(" | ")[0] if alt_text else ""
                    if ":" in first_alt:
                        alt_source, rest = first_alt.split(":", 1)
                        alt_series = rest.split(" (")[0].strip()
                    else:
                        alt_source, alt_series = "", ""
                    btn_label = f"Swap {metric_key} -> {alt_source}:{alt_series}"[:90]
                    if alt_source and alt_series:
                        if st.button(btn_label, use_container_width=True, key=f"xsrc_revise_alt_{i}"):
                            revised = deepcopy(plan)
                            for m in revised.metrics:
                                if f"{m.source}:{m.series_id}" == metric_key:
                                    m.source = alt_source.strip()
                                    m.series_id = alt_series
                                    m.selection_method = "manual_revise"
                                    m.selection_reason = (
                                        "User accepted automatic alternative due to sparse/missing coverage."
                                    )
                                    break
                            with st.spinner("Re-running with alternative indicator..."):
                                _execute_and_store(
                                    revised,
                                    f"{payload.get('query', '')} (revised: swapped {metric_key} to {alt_source}:{alt_series})",
                                    force_refresh=False,
                                )
                            st.rerun()
            else:
                st.caption("No alternative-swap suggestions available for current metrics.")

        with rev_col3:
            if st.button("Keep Only Overlapping Years", use_container_width=True, key="xsrc_revise_overlap"):
                revised = deepcopy(plan)
                revised.from_year = plan.from_year
                revised.to_year = plan.to_year

                metric_year_sets: list[set[int]] = []
                for metric in revised.metrics:
                    mk = f"{metric.source}:{metric.series_id}"
                    df_m = result.metric_frames.get(mk)
                    if df_m is None or df_m.empty or "year" not in df_m.columns:
                        continue
                    years = pd.to_numeric(df_m["year"], errors="coerce").dropna().astype(int).tolist()
                    ys = {y for y in years if revised.from_year <= y <= revised.to_year}
                    if ys:
                        metric_year_sets.append(ys)

                if len(metric_year_sets) < 2:
                    st.warning("Need at least two metrics with year data to compute overlap.")
                else:
                    overlap = set.intersection(*metric_year_sets) if metric_year_sets else set()
                    if not overlap:
                        st.warning("No overlapping years found across selected metrics.")
                    else:
                        revised.from_year = min(overlap)
                        revised.to_year = max(overlap)
                        with st.spinner(
                            f"Re-running with overlapping years only ({revised.from_year}-{revised.to_year})..."
                        ):
                            _execute_and_store(
                                revised,
                                (
                                    f"{payload.get('query', '')} "
                                    f"(revised: overlap years {revised.from_year}-{revised.to_year})"
                                ),
                                force_refresh=False,
                            )
                        st.rerun()

        numeric_cols = [c for c in merged_df.columns if c not in ("iso3", "country", "geo_group", "scope", "year")]
        numeric_cols = [c for c in numeric_cols if pd.api.types.is_numeric_dtype(merged_df[c])]

        section_divider("Visualization")
        has_geo_group = "geo_group" in merged_df.columns
        if len(numeric_cols) >= 2:
            x_col, y_col = numeric_cols[0], numeric_cols[1]
            c1, c2 = st.columns(2)

            with c1:
                trend_df = merged_df.sort_values("year")
                if has_geo_group:
                    fig_line = px.line(
                        trend_df,
                        x="year",
                        y=x_col,
                        color="geo_group",
                        title=f"{x_col} trend by group",
                        markers=True,
                    )
                else:
                    fig_line = px.line(
                        trend_df,
                        x="year",
                        y=[x_col, y_col],
                        title=f"{x_col} vs {y_col} over time",
                        markers=True,
                    )
                st.plotly_chart(fig_line, use_container_width=True)

            with c2:
                scatter_df = merged_df[[x_col, y_col] + (["geo_group"] if has_geo_group else [])].dropna()
                if len(scatter_df) >= 3:
                    corr = scatter_df[x_col].corr(scatter_df[y_col])
                    fig_scatter = px.scatter(
                        scatter_df,
                        x=x_col,
                        y=y_col,
                        color="geo_group" if has_geo_group else None,
                        trendline="ols",
                        title=f"Correlation scatter ({x_col} vs {y_col})",
                    )
                    st.plotly_chart(fig_scatter, use_container_width=True)
                    st.metric("Pearson correlation", f"{corr:.3f}")
                else:
                    st.info("Not enough overlapping points to compute correlation.")
        elif len(numeric_cols) == 1:
            if has_geo_group:
                fig = px.line(
                    merged_df.sort_values("year"),
                    x="year",
                    y=numeric_cols[0],
                    color="geo_group",
                    markers=True,
                    title=f"{numeric_cols[0]} trend by group",
                )
            else:
                fig = px.line(merged_df.sort_values("year"), x="year", y=numeric_cols[0], markers=True)
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("No numeric metric columns found for charting.")

        section_divider("AI Analysis")
        smart_suggestions = _build_smart_suggestions(merged_df, plan)
        render_analysis_tabs(
            merged_df,
            chat_session_id="cross-source-studio-chat",
            page="generic",
            dataset_name="Cross-Source Dataset",
            suggestions=smart_suggestions,
        )

elif run_clicked and not query.strip():
    st.warning("Enter a query first.")

section_divider("Analysis Assistant")
st.caption("Ask what data to use, how to improve sparse coverage, or how to refine your query.")

for m in st.session_state["xsrc_assistant_chat"]:
    with st.chat_message(m["role"]):
        st.markdown(m["content"])

assistant_input = st.chat_input("Ask the assistant about dataset choice, data gaps, or analysis design...")
if assistant_input:
    st.session_state["xsrc_assistant_chat"].append({"role": "user", "content": assistant_input})

    payload = st.session_state.get("xsrc_last_result")
    plan_ctx = {}
    diagnostics_ctx = []
    if payload:
        p = payload["plan"]
        r = payload["result"]
        plan_ctx = {
            "country": p.country,
            "country_iso3": p.country_iso3,
            "from_year": p.from_year,
            "to_year": p.to_year,
            "purpose": p.purpose,
            "confidence": p.confidence,
            "metrics": [
                {
                    "source": m.source,
                    "series_id": m.series_id,
                    "label": m.label,
                    "selection_method": m.selection_method,
                    "selection_reason": m.selection_reason,
                }
                for m in p.metrics
            ],
        }
        diagnostics_ctx = r.data_diagnostics

    assistant_system = """You are a senior data analysis advisor for a cross-source API analytics studio.

Behavior requirements:
- If user objective is unclear, ask a short clarifying question first.
- Suggest practical datasets/indicators and date ranges.
- If data appears sparse or missing, propose alternatives (proxy indicators or broader date ranges).
- Warn about correlation limits when overlap is too small.
- Keep advice concrete and actionable.
"""

    assistant_human = {
        "user_message": assistant_input,
        "current_plan": plan_ctx,
        "data_diagnostics": diagnostics_ctx,
    }

    try:
        llm = get_llm(temperature=0.2)
        reply = llm.invoke(
            [
                SystemMessage(content=assistant_system),
                HumanMessage(content=json.dumps(assistant_human, default=str)),
            ]
        )
        content = reply.content if hasattr(reply, "content") else str(reply)
    except Exception as exc:
        content = (
            "Assistant is unavailable right now. "
            f"Error: {exc}\n\n"
            "Try refining your query with explicit country, indicators, and year range."
        )

    st.session_state["xsrc_assistant_chat"].append({"role": "assistant", "content": content})
    st.rerun()
