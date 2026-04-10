"""UN Energy Statistics and Energy Balance — data.un.org SDMX API.

Three query modes via tabs:
  🤖 AI Query          — describe what you need; the LLM selects the dataset
                         (Statistics / Balance / both), countries, and years.
  📊 Energy Statistics — manual: 75 commodities × 216 transactions (unit: TN)
  ⚖️ Energy Balance    — manual: 11 commodity groups × 53 transactions (unit: TJ)

AI results are displayed within the AI tab.
Manual results are displayed within their respective tabs.
Each result section includes: dataset table → data availability heatmap →
AI analysis & chat → PyGWalker explorer.
"""

import streamlit as st

from app.components.analysis import render_analysis_tabs
from app.components.charts import show_data_availability_heatmap
from app.components.query_suggestions import render_query_suggestions
from app.components.styles import page_header, section_divider
from app.components.tables import show_pygwalker
from app.services.geo_service import get_iso_reference_df
from app.services.undata_service import (
    ENERGY_QUERY_SUGGESTIONS,
    fetch_energy_balance,
    fetch_energy_stats,
    generate_undata_suggestions,
    get_all_m49,
    parse_energy_query_with_llm,
)

page_header(
    "⚡",
    "UN Energy Statistics",
    "Energy production, trade, transformation and consumption — AI-powered or manual exploration.",
    badge="AI",
)

tab_ai, tab_stats, tab_balance = st.tabs([
    "🤖 AI Query",
    "📊 Energy Statistics",
    "⚖️ Energy Balance",
])

# ===========================================================================
# Country selector helper (Region → Country cascade, all countries, WB-style)
# ===========================================================================

def _render_country_selector(widget_key: str) -> tuple[str, ...]:
    """Render a region → country cascade for all countries and return M49 codes.

    Selecting a region auto-populates the country multiselect (same as WB dashboard).
    Cascade is driven by comparing the current region selection against the
    previously stored value: when it differs, the country key is popped from
    session state so Streamlit falls back to `default=<new region's countries>`
    on the very same render pass — no extra rerun needed.
    """
    iso_df = get_iso_reference_df()
    all_countries = iso_df.dropna(subset=["m49"])
    m49_map = get_all_m49()  # {m49_str: country_name}

    regions = sorted(all_countries["Region Name"].dropna().unique())
    region_key = f"{widget_key}_regions"
    country_key = widget_key
    prev_key = f"{widget_key}_prev_regions"

    sel_regions = st.multiselect(
        "Region:",
        ["SELECT ALL"] + regions,
        label_visibility="collapsed",
        placeholder="Filter by region (optional)",
        key=region_key,
    )
    if "SELECT ALL" in sel_regions:
        effective = list(regions)
    else:
        effective = [r for r in sel_regions if r != "SELECT ALL"]

    # If region selection changed, clear country state before the widget renders
    # so Streamlit uses default= (the new region's countries) instead of stale state.
    if set(st.session_state.get(prev_key, [])) != set(effective):
        st.session_state[prev_key] = list(effective)
        st.session_state.pop(country_key, None)

    # Build defaults from selected regions
    default_m49: list[str] = []
    for region in effective:
        codes = all_countries.loc[all_countries["Region Name"] == region, "m49"].tolist()
        default_m49.extend(str(int(float(c))) for c in codes)
    default_m49 = list(set(default_m49))

    available = sorted(f"{name} ({code})" for code, name in m49_map.items())
    defaults = sorted(f"{m49_map[m]} ({m})" for m in default_m49 if m in m49_map)

    selected_labels = st.multiselect(
        "Countries:",
        available,
        default=defaults,
        label_visibility="collapsed",
        placeholder="Select countries…",
        key=country_key,
    )
    return tuple(lbl.split("(")[-1].rstrip(")") for lbl in selected_labels)


def _render_results(
    df,
    chat_key: str,
    page_key: str,
    dataset_name: str,
    unit_label: str,
    commodity_widget_key: str,
    transaction_widget_key: str,
    suggestions_key: str,
    suggestions_hash_key: str,
) -> None:
    """Render the full results section for a single energy dataset."""
    if df is None or df.empty:
        return

    # Post-fetch filters
    with st.expander("Filter by Commodity / Transaction", expanded=False):
        col_a, col_b = st.columns(2)
        with col_a:
            commodity_opts = (
                sorted(df["COMMODITY"].dropna().unique().tolist())
                if "COMMODITY" in df.columns else []
            )
            sel_commodities = st.multiselect(
                "Commodity:", commodity_opts, default=commodity_opts,
                key=commodity_widget_key,
            )
        with col_b:
            transaction_opts = (
                sorted(df["TRANSACTION"].dropna().unique().tolist())
                if "TRANSACTION" in df.columns else []
            )
            sel_transactions = st.multiselect(
                "Transaction:", transaction_opts, default=transaction_opts,
                key=transaction_widget_key,
            )

    df_view = df.copy()
    if sel_commodities and "COMMODITY" in df_view.columns:
        df_view = df_view[df_view["COMMODITY"].isin(sel_commodities)]
    if sel_transactions and "TRANSACTION" in df_view.columns:
        df_view = df_view[df_view["TRANSACTION"].isin(sel_transactions)]

    section_divider("Dataset")
    col_info, col_sort_col, col_sort_dir, col_dl = st.columns([3, 2, 1, 1])
    with col_info:
        st.caption(f"{len(df_view):,} rows · {len(df_view.columns)} columns · Unit: {unit_label}")
    with col_sort_col:
        sort_col = st.selectbox(
            "Sort by:", df_view.columns.tolist(), index=0,
            label_visibility="collapsed", key=f"{commodity_widget_key}_sort_col",
        )
    with col_sort_dir:
        asc = st.selectbox(
            "Order:", ["ASC", "DESC"], index=0,
            label_visibility="collapsed", key=f"{commodity_widget_key}_sort_dir",
        ) == "ASC"
    with col_dl:
        st.download_button(
            "⬇ CSV",
            data=df_view.to_csv(index=False).encode("utf-8"),
            file_name=f"{dataset_name.replace(' ', '_').lower()}.csv",
            mime="text/csv",
            use_container_width=True,
            key=f"{commodity_widget_key}_dl",
        )
    st.dataframe(df_view.sort_values(sort_col, ascending=asc), use_container_width=True)

    section_divider("Data Availability")
    show_data_availability_heatmap(df_view)

    section_divider("AI Analysis & Visualizations")
    cache_key = hash(str(df.shape) + str(df.columns.tolist()))
    if (
        suggestions_key not in st.session_state
        or st.session_state.get(suggestions_hash_key) != cache_key
    ):
        with st.spinner("Generating suggestions…"):
            qs, vs = generate_undata_suggestions(df_view, dataset_name)
            st.session_state[suggestions_key] = (qs, vs)
            st.session_state[suggestions_hash_key] = cache_key
    else:
        qs, vs = st.session_state[suggestions_key]

    render_analysis_tabs(
        df_view,
        chat_key,
        page=page_key,
        dataset_name=dataset_name,
        suggestions=qs + vs,
    )

    section_divider("PyGWalker Explorer")
    show_pygwalker(df_view)


# ===========================================================================
# Tab 1 — AI Query
# ===========================================================================
with tab_ai:
    st.markdown(
        "**Describe the energy data you need in plain English.** "
        "The AI will choose the right dataset (Statistics or Balance), countries, and years."
    )

    ai_query = render_query_suggestions(
        ENERGY_QUERY_SUGGESTIONS,
        text_area_key="energy_ai_query",
        default_index=0,
        placeholder="e.g., electricity production from renewables in East Africa 2015–2022",
    )

    if st.button("🔍 Fetch Data", type="primary", use_container_width=True, key="energy_ai_fetch") and ai_query:
        with st.spinner("Analysing your query…"):
            parsed = parse_energy_query_with_llm(ai_query)

        if parsed:
            dataset_label = {
                "stats": "Energy Statistics",
                "balance": "Energy Balance",
                "both": "Energy Statistics + Energy Balance",
            }.get(parsed["dataset"], parsed["dataset"])

            with st.expander("📋 Extracted Parameters", expanded=True):
                st.write(f"**Dataset:** {dataset_label}")
                st.write(f"**Countries:** {parsed['country_names']}")
                st.write(f"**Years:** {parsed['start_year']} – {parsed['end_year']}")
                st.write(f"**Explanation:** {parsed['explanation']}")

            m49_tup = parsed["m49_codes"]
            sy, ey = parsed["start_year"], parsed["end_year"]

            if parsed["dataset"] in ("stats", "both"):
                with st.spinner(f"Fetching energy statistics for {len(m49_tup)} countries ({sy}–{ey})…"):
                    df_s = fetch_energy_stats(m49_tup, sy, ey)
                if df_s is not None and not df_s.empty:
                    st.session_state["energy_ai_stats_df"] = df_s
                else:
                    st.session_state.pop("energy_ai_stats_df", None)
                    if parsed["dataset"] == "stats":
                        st.info("No energy statistics data returned. Try different countries or a wider year range.")

            if parsed["dataset"] in ("balance", "both"):
                with st.spinner(f"Fetching energy balance for {len(m49_tup)} countries ({sy}–{ey})…"):
                    df_b = fetch_energy_balance(m49_tup, sy, ey)
                if df_b is not None and not df_b.empty:
                    st.session_state["energy_ai_balance_df"] = df_b
                else:
                    st.session_state.pop("energy_ai_balance_df", None)
                    if parsed["dataset"] == "balance":
                        st.info("No energy balance data returned. Try different countries or a wider year range.")

            st.rerun()

    # AI Results — Statistics
    df_ai_stats = st.session_state.get("energy_ai_stats_df")
    if df_ai_stats is not None and not df_ai_stats.empty:
        section_divider("Energy Statistics Results")
        st.caption("**Source:** UN Energy Statistics Database (`DF_UNDATA_ENERGY`) · Unit: thousands of metric tonnes")
        _render_results(
            df_ai_stats,
            chat_key="energy-ai-stats-chat",
            page_key="energy_stats",
            dataset_name="UN Energy Statistics",
            unit_label="thousands of metric tonnes",
            commodity_widget_key="energy_ai_stats_commodity",
            transaction_widget_key="energy_ai_stats_transaction",
            suggestions_key="energy_ai_stats_suggestions",
            suggestions_hash_key="energy_ai_stats_hash",
        )

    # AI Results — Balance
    df_ai_balance = st.session_state.get("energy_ai_balance_df")
    if df_ai_balance is not None and not df_ai_balance.empty:
        section_divider("Energy Balance Results")
        st.caption("**Source:** UN Energy Balance (`DF_UNData_EnergyBalance`) · Unit: Terajoules")
        _render_results(
            df_ai_balance,
            chat_key="energy-ai-balance-chat",
            page_key="energy_balance",
            dataset_name="UN Energy Balance",
            unit_label="Terajoules",
            commodity_widget_key="energy_ai_balance_commodity",
            transaction_widget_key="energy_ai_balance_transaction",
            suggestions_key="energy_ai_balance_suggestions",
            suggestions_hash_key="energy_ai_balance_hash",
        )

    if df_ai_stats is None and df_ai_balance is None:
        if not any(k in st.session_state for k in ("energy_ai_stats_df", "energy_ai_balance_df")):
            st.info("Select a suggestion or type a query above, then click **🔍 Fetch Data**.")


# ===========================================================================
# Tab 2 — Energy Statistics (Manual)
# ===========================================================================
with tab_stats:
    st.markdown(
        "**Source:** UN Energy Statistics Database (`DF_UNDATA_ENERGY`) — "
        "production, imports, exports, transformation and final consumption "
        "of 75 energy commodities. Unit: thousands of metric tonnes (TN)."
    )

    section_divider("Countries")
    selected_m49_stats = _render_country_selector("energy_stats_countries")

    section_divider("Time Range")
    years_stats = st.slider(
        "Years:", min_value=1990, max_value=2023, value=(2010, 2023),
        label_visibility="collapsed", key="energy_stats_years",
    )

    if not selected_m49_stats:
        st.warning("Select at least one country.")
    else:
        st.caption(
            f"{len(selected_m49_stats)} countries selected · fetches all 75 commodities × 216 transactions "
            f"({years_stats[0]}–{years_stats[1]}). Narrow countries or years to speed up loading."
        )

        _, col_btn = st.columns([3, 1])
        with col_btn:
            fetch_stats = st.button(
                "Get Data", type="primary", use_container_width=True, key="energy_stats_fetch"
            )

        if fetch_stats:
            with st.spinner(
                f"Fetching energy statistics for {len(selected_m49_stats)} countries "
                f"({years_stats[0]}–{years_stats[1]})…"
            ):
                df_stats = fetch_energy_stats(selected_m49_stats, years_stats[0], years_stats[1])
            if df_stats is not None and not df_stats.empty:
                st.session_state["energy_stats_df"] = df_stats
            else:
                st.session_state.pop("energy_stats_df", None)
                st.info("No data returned. Try different countries or a wider year range.")

    df_stats = st.session_state.get("energy_stats_df")
    _render_results(
        df_stats,
        chat_key="energy-manual-stats-chat",
        page_key="energy_stats",
        dataset_name="UN Energy Statistics",
        unit_label="thousands of metric tonnes",
        commodity_widget_key="energy_stats_commodity",
        transaction_widget_key="energy_stats_transaction",
        suggestions_key="energy_stats_suggestions",
        suggestions_hash_key="energy_stats_hash",
    )


# ===========================================================================
# Tab 3 — Energy Balance (Manual)
# ===========================================================================
with tab_balance:
    st.markdown(
        "**Source:** UN Energy Balance (`DF_UNData_EnergyBalance`) — "
        "standardised energy balance by commodity group and transaction type. "
        "Unit: Terajoules (heat content, standardised)."
    )

    section_divider("Countries")
    selected_m49_balance = _render_country_selector("energy_balance_countries")

    section_divider("Time Range")
    years_balance = st.slider(
        "Years:", min_value=1990, max_value=2023, value=(2010, 2023),
        label_visibility="collapsed", key="energy_balance_years",
    )

    if not selected_m49_balance:
        st.warning("Select at least one country.")
    else:
        st.caption(
            f"{len(selected_m49_balance)} countries selected · fetches all 11 commodity groups × 53 transactions "
            f"({years_balance[0]}–{years_balance[1]})."
        )

        _, col_btn2 = st.columns([3, 1])
        with col_btn2:
            fetch_balance = st.button(
                "Get Data", type="primary", use_container_width=True, key="energy_balance_fetch"
            )

        if fetch_balance:
            with st.spinner(
                f"Fetching energy balance for {len(selected_m49_balance)} countries "
                f"({years_balance[0]}–{years_balance[1]})…"
            ):
                df_balance = fetch_energy_balance(selected_m49_balance, years_balance[0], years_balance[1])
            if df_balance is not None and not df_balance.empty:
                st.session_state["energy_balance_df"] = df_balance
            else:
                st.session_state.pop("energy_balance_df", None)
                st.info("No data returned. Try different countries or a wider year range.")

    df_balance = st.session_state.get("energy_balance_df")
    _render_results(
        df_balance,
        chat_key="energy-manual-balance-chat",
        page_key="energy_balance",
        dataset_name="UN Energy Balance",
        unit_label="Terajoules",
        commodity_widget_key="energy_balance_commodity",
        transaction_widget_key="energy_balance_transaction",
        suggestions_key="energy_balance_suggestions",
        suggestions_hash_key="energy_balance_hash",
    )
