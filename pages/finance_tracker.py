"""Finance Tracker — upload CSV statements and visualize spending."""

from __future__ import annotations

import pandas as pd
import plotly.express as px
import streamlit as st

from categories import enrich_categories
from filters import FilterAudit, apply_transaction_filters_with_audit
from merchant_rules import RULES_PATH
from merchants import finalize_spending
from parser import parse_uploaded_files

st.title("Finance Tracker")
st.caption(
    "Step 2: Upload CSV files to see where your money goes. "
    "Have PDF statements? Convert them first in **PDF to CSV** (sidebar)."
)

with st.sidebar:
    st.markdown("### Options")
    auto_categorize = st.toggle(
        "Auto-categorize unknown merchants (online)",
        value=True,
        help="When a merchant is still 'Other' after built-in rules, looks up the category "
        "online once and saves it to `.cache/merchant_lookup.json`. "
        "Only the merchant name is sent (e.g. 'Oates Energy business').",
    )
    st.markdown("### Privacy")
    st.markdown(
        """
        **PDF → CSV** and **CSV analysis** run **entirely on this machine**.
        Your statement files are **not uploaded** to our servers.

        If auto-categorize is **off**, **nothing** is sent to the internet.

        If auto-categorize is **on** (default), only short merchant names are searched
        and results are cached locally in `.cache/merchant_lookup.json`.

        **Manual fixes:** edit `.cache/merchant_rules.json` to override a merchant
        name or category without changing code.
        """
    )
    st.caption(f"Rules file: `{RULES_PATH}`")
    st.markdown(
        "**Tip:** Click a category on any chart to see all charges in that category."
    )


def load_transactions(
    file_bytes: list[tuple[str, bytes]],
    *,
    auto_categorize_unknown: bool,
) -> tuple[pd.DataFrame, FilterAudit, float]:
    class _Upload:
        def __init__(self, name: str, data: bytes):
            self.name = name
            self._data = data

        def getvalue(self) -> bytes:
            return self._data

    uploads = [_Upload(name, data) for name, data in file_bytes]
    raw = parse_uploaded_files(uploads)
    csv_total = float(raw["amount"].sum())
    filtered, audit = apply_transaction_filters_with_audit(raw)
    enriched = enrich_categories(
        filtered,
        auto_categorize_unknown=auto_categorize_unknown,
        audit=audit,
        net_refunds=False,
    )
    return enriched, audit, csv_total


def category_color_map(categories: list[str]) -> dict[str, str]:
    palette = px.colors.qualitative.Set3
    return {category: palette[index % len(palette)] for index, category in enumerate(categories)}


def format_currency(value: float) -> str:
    return f"${value:,.2f}"


def _category_from_chart_event(event) -> str | None:
    if not event or not event.selection or not event.selection.points:
        return None
    point = event.selection.points[0]
    return point.get("label") or point.get("y") or point.get("legendgroup")


def _assign_trend_periods(frame: pd.DataFrame, start_date, end_date) -> pd.DataFrame:
    days = (end_date - start_date).days + 1
    result = frame.copy()
    if days <= 45:
        result["trend_sort"] = result["date"].dt.floor("D")
        result["trend_period"] = result["trend_sort"].dt.strftime("%b %d, %Y")
    elif days <= 120:
        result["trend_sort"] = result["date"].dt.to_period("W").apply(lambda p: p.start_time)
        result["trend_period"] = result["trend_sort"].dt.strftime("%b %d, %Y")
    else:
        result["trend_sort"] = result["date"].dt.to_period("M").apply(lambda p: p.start_time)
        result["trend_period"] = result["trend_sort"].dt.strftime("%b %Y")
    return result


def _spending_trend_frame(spending: pd.DataFrame, start_date, end_date) -> tuple[pd.DataFrame, str]:
    frame = spending.copy()
    if "trend_period" not in frame.columns:
        frame = _assign_trend_periods(frame, start_date, end_date)
    days = (end_date - start_date).days + 1
    if days <= 45:
        label = "Day"
    elif days <= 120:
        label = "Week"
    else:
        label = "Month"
    grouped = (
        frame.groupby(["trend_sort", "trend_period"], as_index=False)["spend_amount"]
        .sum()
        .sort_values("trend_sort")
    )
    return grouped.rename(columns={"trend_period": "period"}), label


def _period_from_chart_event(event) -> str | None:
    if not event or not event.selection or not event.selection.points:
        return None
    point = event.selection.points[0]
    return point.get("x") or point.get("label")


if "selected_category" not in st.session_state:
    st.session_state.selected_category = None
if "selected_trend_period" not in st.session_state:
    st.session_state.selected_trend_period = None


uploaded_files = st.file_uploader(
    "Upload credit card statement CSV files",
    type=["csv"],
    accept_multiple_files=True,
    help="Upload bank CSV exports or CSV files downloaded from PDF to CSV. Multiple files are combined.",
)

if not uploaded_files:
    st.info("Upload at least one CSV to see your spending breakdown.")
    with st.expander("Where do I get a CSV?"):
        st.markdown(
            """
            - **PDF statements:** use **PDF to CSV** in the sidebar to convert them first
            - **Bank export:** download CSV from Chase, Amex, Citi, Apple Card, etc.
            - **Apple Card:** Wallet → statement → **Export Transactions**

            The app accepts standard bank CSVs and CSVs produced by the PDF converter
            (`Transaction Date`, `Description`, `Category`, `Amount`, `Source File`).
            """
        )
    st.stop()

file_payload = [(f.name, f.getvalue()) for f in uploaded_files]

try:
    spinner_msg = " (categorizing new merchants online)" if auto_categorize else ""
    with st.spinner(f"Processing statements...{spinner_msg}"):
        line_items, filter_audit, csv_total = load_transactions(
            file_payload,
            auto_categorize_unknown=auto_categorize,
        )
except ValueError as exc:
    st.error(str(exc))
    st.stop()

pre_enrich = (
    filter_audit.raw_count
    - len(filter_audit.autopay_removed)
    - len(filter_audit.duplicates_removed)
)
st.caption(
    f"CSV column total: **{format_currency(csv_total)}** · "
    f"**{len(line_items):,}** categorized rows from **{pre_enrich:,}** transactions"
)

removed_parts = []
if len(filter_audit.autopay_removed):
    removed_parts.append(f"{len(filter_audit.autopay_removed)} autopay")
if len(filter_audit.duplicates_removed):
    removed_parts.append(f"{len(filter_audit.duplicates_removed)} duplicates")
if len(filter_audit.junk_removed):
    removed_parts.append(f"{len(filter_audit.junk_removed)} junk")

if removed_parts:
    with st.expander(f"Removed or adjusted ({', '.join(removed_parts)})", expanded=False):
        sections = [
            ("Autopay payments", filter_audit.autopay_removed),
            ("Duplicate rows", filter_audit.duplicates_removed),
            ("Unparseable junk", filter_audit.junk_removed),
        ]
        for title, frame in sections:
            if frame is None or frame.empty:
                continue
            st.markdown(f"**{title}** ({len(frame)})")
            display_cols = [c for c in ["date", "description", "merchant", "amount", "reason"] if c in frame.columns]
            if not display_cols:
                display_cols = [c for c in ["date", "description", "amount"] if c in frame.columns]
            st.dataframe(frame[display_cols], use_container_width=True, hide_index=True)

min_date = line_items["date"].min().date()
max_date = line_items["date"].max().date()

if "filter_start" not in st.session_state:
    st.session_state.filter_start = min_date
if "filter_end" not in st.session_state:
    st.session_state.filter_end = max_date

st.subheader("Filters")
filter_col1, filter_col2, filter_col3 = st.columns([2, 2, 1])
with filter_col1:
    start_date = st.date_input(
        "Start date",
        min_value=min_date,
        max_value=max_date,
        key="filter_start",
    )
with filter_col2:
    end_date = st.date_input(
        "End date",
        min_value=min_date,
        max_value=max_date,
        key="filter_end",
    )
with filter_col3:
    st.write("")
    st.write("")
    if st.button("Clear dates", use_container_width=True):
        st.session_state.filter_start = min_date
        st.session_state.filter_end = max_date
        st.session_state.selected_trend_period = None
        st.rerun()

if start_date > end_date:
    start_date, end_date = end_date, start_date

filtered_items = line_items[
    (line_items["date"].dt.date >= start_date) & (line_items["date"].dt.date <= end_date)
].copy()

range_audit = FilterAudit()
spending = finalize_spending(filtered_items, audit=range_audit)
spending = spending[spending["is_spending"]].copy()
spending = _assign_trend_periods(spending, start_date, end_date)

if spending.empty:
    st.warning("No spending transactions found for the selected date range.")
    st.stop()

report_total = float(spending["spend_amount"].sum())
st.caption(f"Report total for selected dates: **{format_currency(report_total)}**")

if len(range_audit.refunds_absorbed) or len(range_audit.fully_refunded):
    with st.expander("Refunds netted in this date range", expanded=False):
        if len(range_audit.refunds_absorbed):
            st.dataframe(range_audit.refunds_absorbed, use_container_width=True, hide_index=True)
        if len(range_audit.fully_refunded):
            st.dataframe(range_audit.fully_refunded, use_container_width=True, hide_index=True)

total_spend = spending["spend_amount"].sum()
txn_count = len(spending)
avg_txn = spending["spend_amount"].mean()
top_category_row = (
    spending.groupby("spend_category", as_index=False)["spend_amount"]
    .sum()
    .sort_values("spend_amount", ascending=False)
    .iloc[0]
)

st.success(
    f"**{start_date.strftime('%b %d, %Y')}** – **{end_date.strftime('%b %d, %Y')}** · "
    f"**{txn_count:,}** netted spending rows · "
    f"**{filtered_items['source_file'].nunique()}** source file(s)"
)

col1, col2, col3, col4 = st.columns(4)
col1.metric("Total spending", format_currency(total_spend))
col2.metric("Transactions", f"{txn_count:,}")
col3.metric("Avg transaction", format_currency(avg_txn))
col4.metric("Top category", top_category_row["spend_category"], format_currency(top_category_row["spend_amount"]))

st.divider()

chart_left, chart_right = st.columns(2)

by_category = (
    spending.groupby("spend_category", as_index=False)["spend_amount"]
    .sum()
    .sort_values("spend_amount", ascending=False)
)
by_category["share"] = by_category["spend_amount"] / by_category["spend_amount"].sum() * 100
color_map = category_color_map(by_category["spend_category"].tolist())

with chart_left:
    st.subheader("Spending by category")
    fig_pie = px.pie(
        by_category,
        names="spend_category",
        values="spend_amount",
        hole=0.45,
        color="spend_category",
        color_discrete_map=color_map,
    )
    fig_pie.update_traces(textposition="inside", textinfo="percent+label")
    fig_pie.update_layout(margin=dict(t=20, b=20, l=20, r=20), showlegend=False)
    pie_event = st.plotly_chart(
        fig_pie,
        use_container_width=True,
        on_select="rerun",
        selection_mode="points",
        key="category_pie",
    )
    picked = _category_from_chart_event(pie_event)
    if picked:
        st.session_state.selected_category = picked

with chart_right:
    st.subheader("Highest-spend categories")
    bar_data = by_category.head(10).copy()
    bar_data["amount_label"] = bar_data["spend_amount"].map(format_currency)
    fig_bar = px.bar(
        bar_data,
        x="spend_amount",
        y="spend_category",
        orientation="h",
        color="spend_category",
        color_discrete_map=color_map,
        text="amount_label",
    )
    fig_bar.update_layout(
        yaxis={"categoryorder": "total ascending"},
        xaxis=dict(showticklabels=False, title=""),
        margin=dict(t=20, b=20, l=20, r=20),
    )
    fig_bar.update_traces(textposition="outside", cliponaxis=False)
    bar_event = st.plotly_chart(
        fig_bar,
        use_container_width=True,
        on_select="rerun",
        selection_mode="points",
        key="category_bar",
    )
    picked = _category_from_chart_event(bar_event)
    if picked:
        st.session_state.selected_category = picked

if st.session_state.selected_category:
    selected = st.session_state.selected_category
    cat_total = spending.loc[spending["spend_category"] == selected, "spend_amount"].sum()
    hdr_col, btn_col = st.columns([4, 1])
    with hdr_col:
        st.subheader(f"{selected} — {format_currency(cat_total)}")
    with btn_col:
        if st.button("Clear", key="clear_category"):
            st.session_state.selected_category = None
            st.rerun()
    cat_rows = spending[spending["spend_category"] == selected][
        ["date", "merchant", "description", "spend_amount", "source_file"]
    ].sort_values("date", ascending=False)
    st.dataframe(
        cat_rows,
        use_container_width=True,
        column_config={
            "date": st.column_config.DateColumn("Date"),
            "merchant": "Merchant",
            "description": "Original description",
            "spend_amount": st.column_config.NumberColumn("Amount", format="$%.2f"),
            "source_file": "Source file",
        },
        hide_index=True,
    )
    st.divider()

trend_frame, trend_label = _spending_trend_frame(spending, start_date, end_date)
st.subheader("Spending trend")
fig_line = px.bar(
    trend_frame,
    x="period",
    y="spend_amount",
    labels={"period": trend_label, "spend_amount": "Spending ($)"},
)
fig_line.update_layout(
    margin=dict(t=20, b=20, l=20, r=20),
    xaxis_title=trend_label,
    yaxis_title="Spending ($)",
    xaxis={"categoryorder": "array", "categoryarray": trend_frame["period"].tolist()},
)
fig_line.update_traces(text=None)
trend_event = st.plotly_chart(
    fig_line,
    use_container_width=True,
    on_select="rerun",
    selection_mode="points",
    key="trend_bar",
)
picked_period = _period_from_chart_event(trend_event)
if picked_period:
    st.session_state.selected_trend_period = picked_period

if st.session_state.selected_trend_period:
    period_label = st.session_state.selected_trend_period
    period_rows = spending[spending["trend_period"] == period_label].copy()
    period_total = float(period_rows["spend_amount"].sum())
    hdr_col, btn_col = st.columns([4, 1])
    with hdr_col:
        st.subheader(f"{period_label} — {format_currency(period_total)}")
    with btn_col:
        if st.button("Clear", key="clear_trend_period"):
            st.session_state.selected_trend_period = None
            st.rerun()
    period_display = period_rows[
        ["date", "merchant", "description", "spend_category", "spend_amount", "source_file"]
    ].sort_values("date", ascending=False)
    st.dataframe(
        period_display,
        use_container_width=True,
        column_config={
            "date": st.column_config.DateColumn("Date"),
            "merchant": "Merchant",
            "description": "Original description",
            "spend_category": "Category",
            "spend_amount": st.column_config.NumberColumn("Amount", format="$%.2f"),
            "source_file": "Source file",
        },
        hide_index=True,
    )

st.divider()

tab_merchants, tab_all, tab_sources = st.tabs(
    ["Top merchants", "All transactions", "By source file"]
)

active_category = st.session_state.selected_category

with tab_merchants:
    st.subheader("Where the money goes — top merchants")
    category_options = ["All categories"] + by_category["spend_category"].tolist()
    default_index = 0
    if active_category and active_category in category_options:
        default_index = category_options.index(active_category)
    selected_category = st.selectbox(
        "Filter by category",
        options=category_options,
        index=default_index,
        key="merchant_category_filter",
    )
    merchant_spending = spending
    if selected_category != "All categories":
        merchant_spending = spending[spending["spend_category"] == selected_category]

    if merchant_spending.empty:
        st.info(f"No spending in **{selected_category}** for this date range.")
    else:
        by_merchant = (
            merchant_spending.groupby(["merchant", "spend_category"], as_index=False)["spend_amount"]
            .sum()
            .sort_values("spend_amount", ascending=False)
            .head(25)
        )
        by_merchant["amount_label"] = by_merchant["spend_amount"].map(format_currency)
        fig_merchants = px.bar(
            by_merchant,
            x="spend_amount",
            y="merchant",
            orientation="h",
            color="spend_category",
            color_discrete_map=color_map,
            text="amount_label",
            labels={"spend_amount": "Amount ($)", "merchant": "Merchant", "spend_category": "Category"},
        )
        fig_merchants.update_layout(
            yaxis={"categoryorder": "total ascending"},
            xaxis=dict(showticklabels=False, title=""),
            margin=dict(t=20, b=20, l=20, r=20),
            legend_title_text="Category",
        )
        fig_merchants.update_traces(textposition="outside", cliponaxis=False)
        merchant_event = st.plotly_chart(
            fig_merchants,
            use_container_width=True,
            on_select="rerun",
            selection_mode="points",
            key="merchant_bar",
        )
        picked = _category_from_chart_event(merchant_event)
        if picked:
            st.session_state.selected_category = picked

with tab_all:
    display = spending[
        ["date", "merchant", "description", "spend_category", "spend_amount", "source_file"]
    ].sort_values("date", ascending=False)
    if active_category:
        display = display[display["spend_category"] == active_category]
    st.dataframe(
        display,
        use_container_width=True,
        column_config={
            "date": st.column_config.DateColumn("Date"),
            "merchant": "Merchant",
            "description": "Original description",
            "spend_category": "Category",
            "spend_amount": st.column_config.NumberColumn("Amount", format="$%.2f"),
            "source_file": "Source file",
        },
        hide_index=True,
    )

with tab_sources:
    by_source = (
        spending.groupby("source_file", as_index=False)
        .agg(transactions=("spend_amount", "count"), total_spend=("spend_amount", "sum"))
        .sort_values("total_spend", ascending=False)
    )
    st.dataframe(
        by_source,
        use_container_width=True,
        column_config={
            "source_file": "File",
            "transactions": "Transactions",
            "total_spend": st.column_config.NumberColumn("Total spend", format="$%.2f"),
        },
        hide_index=True,
    )
