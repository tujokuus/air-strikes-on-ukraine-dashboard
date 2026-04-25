from __future__ import annotations

import html
from datetime import date, timedelta

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from dashboard.data import format_int
from dashboard.date_queries import (
    get_filtered_area_macros,
    get_filtered_daily_activity,
    get_filtered_overview,
    get_filtered_region_map,
    get_filtered_weapon_models,
)
from dashboard.filters import get_selected_date_range


def safe_pct(numerator: float, denominator: float) -> float:
    if not denominator:
        return 0.0
    return 100.0 * numerator / denominator


def format_decimal(value: float, digits: int = 1) -> str:
    return f"{value:,.{digits}f}"


def format_delta(value: float, digits: int = 0, suffix: str = "") -> str:
    if digits == 0:
        return f"{int(round(value)):+,}{suffix}"
    return f"{value:+,.{digits}f}{suffix}"


def format_change_with_pct(
    current: float,
    previous: float,
    digits: int = 0,
    suffix: str = "",
    pct_digits: int = 1,
) -> str:
    absolute_delta = format_delta(current - previous, digits=digits, suffix=suffix)
    if previous == 0:
        percent_delta = "0.0%" if current == 0 else "n/a"
    else:
        percent_delta = f"{(100.0 * (current - previous) / previous):+,.{pct_digits}f}%"
    return f"{absolute_delta} ({percent_delta})"


def get_previous_period_range(start_date: date, end_date: date) -> tuple[date, date]:
    period_days = (end_date - start_date).days + 1
    previous_end = start_date - timedelta(days=1)
    previous_start = previous_end - timedelta(days=period_days - 1)
    return previous_start, previous_end


def build_area_macro_chart(area_macros: pd.DataFrame) -> pd.DataFrame:
    if area_macros.empty:
        return pd.DataFrame(
            columns=[
                "area_macro",
                "attack_rows",
                "active_days",
                "launched_total",
                "destroyed_total",
                "launched_share_pct",
            ]
        )

    chart = (
        area_macros.groupby("area_macro", as_index=False)
        .agg(
            attack_rows=("attack_rows", "sum"),
            active_days=("active_days", "max"),
            launched_total=("launched_total", "sum"),
            destroyed_total=("destroyed_total", "sum"),
        )
        .sort_values(["launched_total", "attack_rows"], ascending=[False, False])
    )
    total_launched = chart["launched_total"].sum()
    chart["launched_share_pct"] = (
        0.0 if total_launched == 0 else (100.0 * chart["launched_total"] / total_launched).round(2)
    )
    return chart


def build_region_focus(region_map: pd.DataFrame) -> pd.DataFrame:
    region_focus = region_map.copy()
    if region_focus.empty:
        region_focus["allocated_share_pct"] = pd.Series(dtype="float64")
        return region_focus

    region_total_allocated = region_focus["launched_total_allocated"].sum()
    region_focus["allocated_share_pct"] = (
        0.0
        if region_total_allocated == 0
        else (100.0 * region_focus["launched_total_allocated"] / region_total_allocated).round(2)
    )
    return region_focus.sort_values(
        ["launched_total_allocated", "attack_rows"],
        ascending=[False, False],
    )


def pct_change_value(current: float, previous: float) -> float | None:
    if previous == 0:
        return 0.0 if current == 0 else None
    return 100.0 * (current - previous) / previous


def pct_change_label(current: float, previous: float, digits: int = 1) -> str:
    value = pct_change_value(current, previous)
    if value is None:
        return "New"
    return f"{value:+,.{digits}f}%"


def build_weapon_model_change_frame(
    current_models: pd.DataFrame,
    comparison_models: pd.DataFrame,
) -> pd.DataFrame:
    current = current_models[
        [
            "weapon_model_key",
            "weapon_model",
            "weapon_category",
            "weapon_type",
            "launched_total",
            "launched_share_pct",
        ]
    ].rename(
        columns={
            "weapon_model": "weapon_model_current",
            "weapon_category": "weapon_category_current",
            "weapon_type": "weapon_type_current",
            "launched_total": "launched_total_current",
            "launched_share_pct": "launched_share_pct_current",
        }
    )
    comparison = comparison_models[
        [
            "weapon_model_key",
            "weapon_model",
            "weapon_category",
            "weapon_type",
            "launched_total",
            "launched_share_pct",
        ]
    ].rename(
        columns={
            "weapon_model": "weapon_model_comparison",
            "weapon_category": "weapon_category_comparison",
            "weapon_type": "weapon_type_comparison",
            "launched_total": "launched_total_comparison",
            "launched_share_pct": "launched_share_pct_comparison",
        }
    )

    merged = current.merge(comparison, on="weapon_model_key", how="outer")
    merged["weapon_model"] = merged["weapon_model_current"].combine_first(merged["weapon_model_comparison"])
    merged["weapon_category"] = merged["weapon_category_current"].combine_first(
        merged["weapon_category_comparison"]
    )
    merged["weapon_type"] = merged["weapon_type_current"].combine_first(
        merged["weapon_type_comparison"]
    )
    merged["launched_total_current"] = merged["launched_total_current"].fillna(0.0)
    merged["launched_total_comparison"] = merged["launched_total_comparison"].fillna(0.0)
    merged["launched_share_pct_current"] = merged["launched_share_pct_current"].fillna(0.0)
    merged["launched_share_pct_comparison"] = merged["launched_share_pct_comparison"].fillna(0.0)
    merged["launched_delta"] = (
        merged["launched_total_current"] - merged["launched_total_comparison"]
    ).round(2)
    merged["share_delta_pct"] = (
        merged["launched_share_pct_current"] - merged["launched_share_pct_comparison"]
    ).round(2)
    merged["delta_pct_label"] = merged.apply(
        lambda row: pct_change_label(
            float(row["launched_total_current"]),
            float(row["launched_total_comparison"]),
        ),
        axis=1,
    )
    merged["status"] = merged.apply(
        lambda row: (
            "New"
            if row["launched_total_comparison"] == 0 and row["launched_total_current"] > 0
            else "Dropped"
            if row["launched_total_current"] == 0 and row["launched_total_comparison"] > 0
            else "Continuing"
        ),
        axis=1,
    )
    return merged.sort_values(
        ["launched_delta", "launched_total_current", "weapon_model"],
        ascending=[False, False, True],
    )


def build_driver_frame(
    current_weapon_models: pd.DataFrame,
    comparison_weapon_models: pd.DataFrame,
    current_area_macros: pd.DataFrame,
    comparison_area_macros: pd.DataFrame,
) -> pd.DataFrame:
    current_categories = current_weapon_models.groupby("weapon_category", as_index=False).agg(
        current_total=("launched_total", "sum")
    )
    comparison_categories = comparison_weapon_models.groupby("weapon_category", as_index=False).agg(
        comparison_total=("launched_total", "sum")
    )
    category_drivers = current_categories.merge(
        comparison_categories,
        on="weapon_category",
        how="outer",
    )
    category_drivers["weapon_category"] = category_drivers["weapon_category"].fillna("Unknown")
    category_drivers["current_total"] = category_drivers["current_total"].fillna(0.0)
    category_drivers["comparison_total"] = category_drivers["comparison_total"].fillna(0.0)
    category_drivers["driver_group"] = "Weapon category"
    category_drivers["driver_name"] = category_drivers["weapon_category"]

    current_macro = current_area_macros[["area_macro", "launched_total"]].rename(
        columns={"launched_total": "current_total"}
    )
    comparison_macro = comparison_area_macros[["area_macro", "launched_total"]].rename(
        columns={"launched_total": "comparison_total"}
    )
    macro_drivers = current_macro.merge(comparison_macro, on="area_macro", how="outer")
    macro_drivers["area_macro"] = macro_drivers["area_macro"].fillna("Unknown")
    macro_drivers["current_total"] = macro_drivers["current_total"].fillna(0.0)
    macro_drivers["comparison_total"] = macro_drivers["comparison_total"].fillna(0.0)
    macro_drivers["driver_group"] = "Area macro"
    macro_drivers["driver_name"] = macro_drivers["area_macro"]

    drivers = pd.concat(
        [
            category_drivers[["driver_group", "driver_name", "current_total", "comparison_total"]],
            macro_drivers[["driver_group", "driver_name", "current_total", "comparison_total"]],
        ],
        ignore_index=True,
    )
    drivers["delta"] = (drivers["current_total"] - drivers["comparison_total"]).round(2)
    drivers["delta_pct_label"] = drivers.apply(
        lambda row: pct_change_label(float(row["current_total"]), float(row["comparison_total"])),
        axis=1,
    )
    return drivers.sort_values(
        ["delta", "current_total", "driver_name"],
        ascending=[False, False, True],
    )


def render_insight_card(title: str, body: str) -> None:
    st.markdown(
        f"""
        <div style="
            border: 1px solid #dbe3ea;
            border-radius: 8px;
            padding: 0.95rem 1rem;
            min-height: 155px;
            background: #fbfdff;
        ">
            <div style="
                font-size: 0.8rem;
                font-weight: 700;
                color: #475569;
                text-transform: uppercase;
                letter-spacing: 0;
            ">{html.escape(title)}</div>
            <div style="
                margin-top: 0.55rem;
                font-size: 0.98rem;
                line-height: 1.5;
                color: #0f172a;
            ">{html.escape(body)}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


st.title("Analysis")
st.caption("Interpretive readouts for tempo, weapon concentration, and target geography.")
selected_start, selected_end = get_selected_date_range()
default_comparison_start, default_comparison_end = get_previous_period_range(selected_start, selected_end)
st.caption(f"Selected range: {selected_start:%d.%m.%Y} - {selected_end:%d.%m.%Y}")

overview = get_filtered_overview(selected_start, selected_end)
daily = get_filtered_daily_activity(selected_start, selected_end)
weapon_models = get_filtered_weapon_models(selected_start, selected_end)
area_macros = get_filtered_area_macros(selected_start, selected_end)
region_map = get_filtered_region_map(selected_start, selected_end)

if daily.empty:
    st.info("No analysis data was found in the selected date range.")
    st.stop()

overall_success_pct = safe_pct(float(overview["total_destroyed"]), float(overview["total_launched"]))
avg_daily_launched = daily["launched_total"].mean()
avg_daily_destroyed = daily["destroyed_total"].mean()

daily = daily.copy()
daily["air_defense_success_pct"] = (
    100.0 * daily["destroyed_total"] / daily["launched_total"].replace({0: pd.NA})
).round(2)
daily["launched_7d"] = daily["launched_total"].rolling(7, min_periods=1).mean()
daily["destroyed_7d"] = daily["destroyed_total"].rolling(7, min_periods=1).mean()
daily["period_day"] = range(1, len(daily) + 1)

peak_day = daily.sort_values(["launched_total", "destroyed_total"], ascending=[False, False]).iloc[0]
peak_multiplier = 0.0 if avg_daily_launched == 0 else peak_day["launched_total"] / avg_daily_launched

top_model = weapon_models.iloc[0] if not weapon_models.empty else None
top_three_share = weapon_models.head(3)["launched_share_pct"].sum() if not weapon_models.empty else 0.0

weapon_category_mix = (
    weapon_models.groupby("weapon_category", as_index=False)
    .agg(
        launched_total=("launched_total", "sum"),
        destroyed_total=("destroyed_total", "sum"),
        attack_rows=("attack_rows", "sum"),
    )
    .sort_values(["launched_total", "attack_rows"], ascending=[False, False])
)
weapon_category_mix["launched_share_pct"] = (
    100.0
    * weapon_category_mix["launched_total"]
    / weapon_category_mix["launched_total"].sum()
).round(2)

top_models_chart = weapon_models.head(10).copy()
top_models_chart["cumulative_share_pct"] = top_models_chart["launched_share_pct"].cumsum().round(2)

area_macros_chart = build_area_macro_chart(area_macros)
region_focus = build_region_focus(region_map)

top_macro = area_macros_chart.iloc[0] if not area_macros_chart.empty else None
top_region = region_focus.iloc[0] if not region_focus.empty else None

summary_col1, summary_col2, summary_col3, summary_col4, summary_col5 = st.columns(5)
summary_col1.metric("Strikes", format_int(overview["total_attack_rows"]))
summary_col2.metric("Launched total", format_int(overview["total_launched"]))
summary_col3.metric("Destroyed total", format_int(overview["total_destroyed"]))
summary_col4.metric("Air defense success", f"{overall_success_pct:.1f}%")
summary_col5.metric("Active days", format_int(overview["distinct_event_dates"]))

tabs = st.tabs(["Summary", "Weapons", "Geography"])

with tabs[0]:
    st.subheader("Key Findings")
    insight_cols = st.columns(3)

    tempo_body = (
        f"Peak pressure came on {peak_day['event_date']:%d.%m.%Y} with "
        f"{format_int(peak_day['launched_total'])} launched. That is "
        f"{peak_multiplier:.1f}x the period average of {format_decimal(avg_daily_launched, 1)} per active day."
    )
    weapon_body = (
        "No weapon model data was available for this range."
        if top_model is None
        else (
            f"{top_model['weapon_model']} was the largest single model with "
            f"{format_int(top_model['launched_total'])} launched "
            f"({top_model['launched_share_pct']:.1f}% share). "
            f"The top three models combined accounted for {top_three_share:.1f}%."
        )
    )
    geography_body = (
        "No mapped region data was available for this range."
        if top_macro is None or top_region is None
        else (
            f"{top_macro['area_macro']} was the largest macro area with "
            f"{format_int(top_macro['launched_total'])} launched "
            f"({top_macro['launched_share_pct']:.1f}% share). "
            f"{top_region['reporting_region']} led mapped regions with "
            f"{format_decimal(top_region['launched_total_allocated'], 1)} allocated launches."
        )
    )

    with insight_cols[0]:
        render_insight_card("Tempo", tempo_body)
    with insight_cols[1]:
        render_insight_card("Weapon Mix", weapon_body)
    with insight_cols[2]:
        render_insight_card("Geography", geography_body)

    st.subheader("Period over Period")
    comparison_range = st.date_input(
        "Comparison range",
        value=(default_comparison_start, default_comparison_end),
        key="analysis_comparison_range",
    )

    if isinstance(comparison_range, tuple):
        if len(comparison_range) != 2:
            st.info("Select both start and end dates for the comparison range.")
            st.stop()
        comparison_start, comparison_end = comparison_range
    else:
        comparison_start = comparison_end = comparison_range

    st.caption(f"Comparison range: {comparison_start:%d.%m.%Y} - {comparison_end:%d.%m.%Y}")

    previous_overview = get_filtered_overview(comparison_start, comparison_end)
    previous_daily = get_filtered_daily_activity(comparison_start, comparison_end)
    previous_weapon_models = get_filtered_weapon_models(comparison_start, comparison_end)
    previous_area_macros = get_filtered_area_macros(comparison_start, comparison_end)
    previous_region_map = get_filtered_region_map(comparison_start, comparison_end)

    previous_overall_success_pct = safe_pct(
        float(previous_overview["total_destroyed"]),
        float(previous_overview["total_launched"]),
    )
    previous_avg_daily_launched = (
        previous_daily["launched_total"].mean() if not previous_daily.empty else 0.0
    )
    previous_avg_daily_destroyed = (
        previous_daily["destroyed_total"].mean() if not previous_daily.empty else 0.0
    )
    previous_top_model = previous_weapon_models.iloc[0] if not previous_weapon_models.empty else None
    previous_top_three_share = (
        previous_weapon_models.head(3)["launched_share_pct"].sum()
        if not previous_weapon_models.empty
        else 0.0
    )
    previous_area_macros_chart = build_area_macro_chart(previous_area_macros)
    previous_region_focus = build_region_focus(previous_region_map)
    previous_top_macro = (
        previous_area_macros_chart.iloc[0] if not previous_area_macros_chart.empty else None
    )
    previous_top_region = previous_region_focus.iloc[0] if not previous_region_focus.empty else None

    previous_daily = previous_daily.copy()
    if not previous_daily.empty:
        previous_daily["air_defense_success_pct"] = (
            100.0
            * previous_daily["destroyed_total"]
            / previous_daily["launched_total"].replace({0: pd.NA})
        ).round(2)
        previous_daily["launched_7d"] = previous_daily["launched_total"].rolling(7, min_periods=1).mean()
        previous_daily["destroyed_7d"] = previous_daily["destroyed_total"].rolling(7, min_periods=1).mean()
        previous_daily["period_day"] = range(1, len(previous_daily) + 1)

    weapon_model_changes = build_weapon_model_change_frame(weapon_models, previous_weapon_models)
    drivers_of_change = build_driver_frame(
        weapon_models,
        previous_weapon_models,
        area_macros_chart,
        previous_area_macros_chart,
    )

    pop_cols = st.columns(5)
    pop_cols[0].metric(
        "Strikes",
        format_int(overview["total_attack_rows"]),
        delta=format_change_with_pct(
            float(overview["total_attack_rows"]),
            float(previous_overview["total_attack_rows"]),
        ),
    )
    pop_cols[1].metric(
        "Launched total",
        format_int(overview["total_launched"]),
        delta=format_change_with_pct(
            float(overview["total_launched"]),
            float(previous_overview["total_launched"]),
        ),
    )
    pop_cols[2].metric(
        "Destroyed total",
        format_int(overview["total_destroyed"]),
        delta=format_change_with_pct(
            float(overview["total_destroyed"]),
            float(previous_overview["total_destroyed"]),
        ),
    )
    pop_cols[3].metric(
        "Air defense success",
        f"{overall_success_pct:.1f}%",
        delta=format_change_with_pct(
            overall_success_pct,
            previous_overall_success_pct,
            digits=1,
            suffix=" pp",
        ),
    )
    pop_cols[4].metric(
        "Avg launched / active day",
        format_decimal(avg_daily_launched, 1),
        delta=format_change_with_pct(
            avg_daily_launched,
            previous_avg_daily_launched,
            digits=1,
        ),
    )

    comparison_frame = pd.DataFrame(
        [
            {"Period": "Selected", "Metric": "Strikes", "Value": float(overview["total_attack_rows"])},
            {"Period": "Previous", "Metric": "Strikes", "Value": float(previous_overview["total_attack_rows"])},
            {"Period": "Selected", "Metric": "Launched total", "Value": float(overview["total_launched"])},
            {"Period": "Previous", "Metric": "Launched total", "Value": float(previous_overview["total_launched"])},
            {"Period": "Selected", "Metric": "Destroyed total", "Value": float(overview["total_destroyed"])},
            {"Period": "Previous", "Metric": "Destroyed total", "Value": float(previous_overview["total_destroyed"])},
            {"Period": "Selected", "Metric": "Avg launched / active day", "Value": float(avg_daily_launched)},
            {"Period": "Previous", "Metric": "Avg launched / active day", "Value": float(previous_avg_daily_launched)},
        ]
    )
    comparison_fig = px.bar(
        comparison_frame,
        x="Metric",
        y="Value",
        color="Period",
        barmode="group",
        color_discrete_map={"Selected": "#9e1e1e", "Previous": "#64748b"},
        title="Selected period vs comparison period",
    )
    comparison_fig.update_layout(xaxis_title="", yaxis_title="Value", legend_title_text="")
    st.plotly_chart(comparison_fig, use_container_width=True)

    comparison_insight_cols = st.columns(3)
    top_model_shift_body = (
        "No previous weapon-model data was available for the comparison period."
        if previous_top_model is None or top_model is None
        else (
            f"Top model shifted from {previous_top_model['weapon_model']} "
            f"({format_int(previous_top_model['launched_total'])} launched) to "
            f"{top_model['weapon_model']} ({format_int(top_model['launched_total'])} launched). "
            f"Top-three concentration moved from {previous_top_three_share:.1f}% to {top_three_share:.1f}%."
        )
    )
    tempo_shift_body = (
        f"Average launched per active day moved from {format_decimal(previous_avg_daily_launched, 1)} "
        f"to {format_decimal(avg_daily_launched, 1)}, while average destroyed moved from "
        f"{format_decimal(previous_avg_daily_destroyed, 1)} to {format_decimal(avg_daily_destroyed, 1)}."
    )
    geography_shift_body = (
        "No previous mapped region data was available for the comparison period."
        if previous_top_macro is None or previous_top_region is None or top_macro is None or top_region is None
        else (
            f"Leading macro area moved from {previous_top_macro['area_macro']} "
            f"({previous_top_macro['launched_share_pct']:.1f}% share) to "
            f"{top_macro['area_macro']} ({top_macro['launched_share_pct']:.1f}% share). "
            f"Top mapped region moved from {previous_top_region['reporting_region']} to "
            f"{top_region['reporting_region']}."
        )
    )

    with comparison_insight_cols[0]:
        render_insight_card("Tempo Shift", tempo_shift_body)
    with comparison_insight_cols[1]:
        render_insight_card("Model Shift", top_model_shift_body)
    with comparison_insight_cols[2]:
        render_insight_card("Geography Shift", geography_shift_body)

    st.subheader("Drivers of Change")
    drivers_increase = (
        drivers_of_change[drivers_of_change["delta"] > 0]
        .head(6)
        .rename(
            columns={
                "driver_group": "Driver group",
                "driver_name": "Driver",
                "current_total": "Selected launched",
                "comparison_total": "Comparison launched",
                "delta": "Delta",
                "delta_pct_label": "Delta %",
            }
        )
    )
    drivers_decline = (
        drivers_of_change[drivers_of_change["delta"] < 0]
        .sort_values(["delta", "comparison_total", "driver_name"], ascending=[True, False, True])
        .head(6)
        .rename(
            columns={
                "driver_group": "Driver group",
                "driver_name": "Driver",
                "current_total": "Selected launched",
                "comparison_total": "Comparison launched",
                "delta": "Delta",
                "delta_pct_label": "Delta %",
            }
        )
    )
    drivers_col1, drivers_col2 = st.columns(2)
    with drivers_col1:
        st.markdown("**Largest increases**")
        if drivers_increase.empty:
            st.info("No positive drivers in the selected comparison.")
        else:
            st.dataframe(drivers_increase, use_container_width=True, hide_index=True)
    with drivers_col2:
        st.markdown("**Largest declines**")
        if drivers_decline.empty:
            st.info("No negative drivers in the selected comparison.")
        else:
            st.dataframe(drivers_decline, use_container_width=True, hide_index=True)

    st.subheader("Operational Tempo")
    tempo_fig = go.Figure()
    tempo_fig.add_scatter(
        x=daily["period_day"],
        y=daily["launched_total"],
        mode="lines",
        name="Selected daily launched",
        line=dict(color="#9e1e1e", width=1.5),
        opacity=0.45,
        customdata=daily[["event_date"]],
        hovertemplate="Selected day %{x}<br>Date %{customdata[0]|%d.%m.%Y}<br>Launched %{y}<extra></extra>",
    )
    tempo_fig.add_scatter(
        x=daily["period_day"],
        y=daily["destroyed_total"],
        mode="lines",
        name="Selected daily destroyed",
        line=dict(color="#2d6a4f", width=1.5),
        opacity=0.45,
        customdata=daily[["event_date"]],
        hovertemplate="Selected day %{x}<br>Date %{customdata[0]|%d.%m.%Y}<br>Destroyed %{y}<extra></extra>",
    )
    tempo_fig.add_scatter(
        x=daily["period_day"],
        y=daily["launched_7d"],
        mode="lines",
        name="Selected 7-day launched avg",
        line=dict(color="#7f1d1d", width=3),
        customdata=daily[["event_date"]],
        hovertemplate="Selected day %{x}<br>Date %{customdata[0]|%d.%m.%Y}<br>7-day launched avg %{y:.1f}<extra></extra>",
    )
    tempo_fig.add_scatter(
        x=daily["period_day"],
        y=daily["destroyed_7d"],
        mode="lines",
        name="Selected 7-day destroyed avg",
        line=dict(color="#166534", width=3),
        customdata=daily[["event_date"]],
        hovertemplate="Selected day %{x}<br>Date %{customdata[0]|%d.%m.%Y}<br>7-day destroyed avg %{y:.1f}<extra></extra>",
    )
    if not previous_daily.empty:
        tempo_fig.add_scatter(
            x=previous_daily["period_day"],
            y=previous_daily["launched_7d"],
            mode="lines",
            name="Comparison 7-day launched avg",
            line=dict(color="#64748b", width=3, dash="dash"),
            customdata=previous_daily[["event_date"]],
            hovertemplate="Comparison day %{x}<br>Date %{customdata[0]|%d.%m.%Y}<br>7-day launched avg %{y:.1f}<extra></extra>",
        )
        tempo_fig.add_scatter(
            x=previous_daily["period_day"],
            y=previous_daily["destroyed_7d"],
            mode="lines",
            name="Comparison 7-day destroyed avg",
            line=dict(color="#94a3b8", width=3, dash="dash"),
            customdata=previous_daily[["event_date"]],
            hovertemplate="Comparison day %{x}<br>Date %{customdata[0]|%d.%m.%Y}<br>7-day destroyed avg %{y:.1f}<extra></extra>",
        )
    tempo_fig.update_layout(
        title="Operational tempo aligned by day in period",
        xaxis_title="Day in period",
        yaxis_title="Count",
        legend_title_text="",
    )
    st.caption(
        "Selected and comparison trends are aligned by relative day in period so different date ranges remain comparable."
    )
    st.plotly_chart(tempo_fig, use_container_width=True)

    st.subheader("Highest-pressure Days")
    surge_days = (
        daily.sort_values(["launched_total", "destroyed_total"], ascending=[False, False])
        .head(10)
        .loc[:, ["event_date", "launched_total", "destroyed_total", "air_defense_success_pct"]]
        .rename(
            columns={
                "event_date": "Date",
                "launched_total": "Launched total",
                "destroyed_total": "Destroyed total",
                "air_defense_success_pct": "Air defense success %",
            }
        )
    )
    st.dataframe(surge_days, use_container_width=True, hide_index=True)

with tabs[1]:
    st.subheader("Weapon Category Mix")
    category_fig = px.bar(
        weapon_category_mix.sort_values("launched_total", ascending=True),
        x="launched_total",
        y="weapon_category",
        orientation="h",
        text="launched_share_pct",
        color="launched_total",
        color_continuous_scale=["#e5eef8", "#91b6db", "#3c79b8", "#1d4f91"],
        labels={
            "weapon_category": "Weapon category",
            "launched_total": "Launched total",
            "launched_share_pct": "Launched share %",
        },
        title="Launched total by weapon category",
    )
    category_fig.update_layout(xaxis_title="Launched total", yaxis_title="Weapon category", coloraxis_showscale=False)
    st.plotly_chart(category_fig, use_container_width=True)

    st.subheader("Top Gainers and Decliners")
    gainers = (
        weapon_model_changes[weapon_model_changes["launched_delta"] > 0]
        .head(10)[
            [
                "weapon_model",
                "weapon_category",
                "launched_total_current",
                "launched_total_comparison",
                "launched_delta",
                "delta_pct_label",
                "status",
            ]
        ]
        .rename(
            columns={
                "weapon_model": "Weapon model",
                "weapon_category": "Category",
                "launched_total_current": "Selected launched",
                "launched_total_comparison": "Comparison launched",
                "launched_delta": "Delta",
                "delta_pct_label": "Delta %",
                "status": "Status",
            }
        )
    )
    decliners = (
        weapon_model_changes[weapon_model_changes["launched_delta"] < 0]
        .sort_values(
            ["launched_delta", "launched_total_comparison", "weapon_model"],
            ascending=[True, False, True],
        )
        .head(10)[
            [
                "weapon_model",
                "weapon_category",
                "launched_total_current",
                "launched_total_comparison",
                "launched_delta",
                "delta_pct_label",
                "status",
            ]
        ]
        .rename(
            columns={
                "weapon_model": "Weapon model",
                "weapon_category": "Category",
                "launched_total_current": "Selected launched",
                "launched_total_comparison": "Comparison launched",
                "launched_delta": "Delta",
                "delta_pct_label": "Delta %",
                "status": "Status",
            }
        )
    )
    movers_col1, movers_col2 = st.columns(2)
    with movers_col1:
        st.markdown("**Top gainers**")
        if gainers.empty:
            st.info("No gaining weapon models in the selected comparison.")
        else:
            st.dataframe(gainers, use_container_width=True, hide_index=True)
    with movers_col2:
        st.markdown("**Top decliners**")
        if decliners.empty:
            st.info("No declining weapon models in the selected comparison.")
        else:
            st.dataframe(decliners, use_container_width=True, hide_index=True)

    st.subheader("Top Model Concentration")
    concentration_fig = go.Figure()
    concentration_fig.add_bar(
        x=top_models_chart["weapon_model"],
        y=top_models_chart["launched_share_pct"],
        name="Launched share %",
        marker_color="#9e1e1e",
    )
    concentration_fig.add_scatter(
        x=top_models_chart["weapon_model"],
        y=top_models_chart["cumulative_share_pct"],
        mode="lines+markers",
        name="Cumulative share %",
        line=dict(color="#1d4f91", width=3),
        yaxis="y2",
    )
    concentration_fig.update_layout(
        title="Top model share and cumulative concentration",
        xaxis_title="Weapon model",
        yaxis=dict(title="Launched share %"),
        yaxis2=dict(title="Cumulative share %", overlaying="y", side="right", range=[0, 100]),
        legend_title_text="",
    )
    st.plotly_chart(concentration_fig, use_container_width=True)

    st.subheader("Model Watchlist")
    st.dataframe(
        weapon_models.head(12)[
            [
                "weapon_model",
                "weapon_category",
                "weapon_type",
                "launched_total",
                "launched_share_pct",
                "destroyed_to_launched_pct",
            ]
        ].rename(
            columns={
                "weapon_model": "Weapon model",
                "weapon_category": "Category",
                "weapon_type": "Type",
                "launched_total": "Launched total",
                "launched_share_pct": "Launched share %",
                "destroyed_to_launched_pct": "Destroyed / launched %",
            }
        ),
        use_container_width=True,
        hide_index=True,
    )

with tabs[2]:
    st.subheader("Macro-area Weight")
    geography_col1, geography_col2 = st.columns(2)

    with geography_col1:
        macro_fig = px.bar(
            area_macros_chart,
            x="area_macro",
            y="launched_total",
            text="launched_share_pct",
            color="launched_total",
            color_continuous_scale=["#fee2e2", "#fca5a5", "#ef4444", "#991b1b"],
            labels={
                "area_macro": "Area macro",
                "launched_total": "Launched total",
                "launched_share_pct": "Launched share %",
            },
            title="Launched total by macro area",
        )
        macro_fig.update_layout(
            xaxis_title="Area macro",
            yaxis_title="Launched total",
            coloraxis_showscale=False,
        )
        st.plotly_chart(macro_fig, use_container_width=True)

    with geography_col2:
        top_regions_chart = region_focus.head(10).sort_values("launched_total_allocated", ascending=True)
        region_fig = px.bar(
            top_regions_chart,
            x="launched_total_allocated",
            y="reporting_region",
            color="area_macro",
            orientation="h",
            text="allocated_share_pct",
            labels={
                "reporting_region": "Reporting region",
                "launched_total_allocated": "Allocated launched total",
                "allocated_share_pct": "Allocated share %",
                "area_macro": "Macro area",
            },
            title="Top mapped regions by allocated launched total",
        )
        region_fig.update_layout(
            xaxis_title="Allocated launched total",
            yaxis_title="Reporting region",
            legend_title_text="",
        )
        st.plotly_chart(region_fig, use_container_width=True)

    st.subheader("Region Focus Table")
    if region_focus.empty:
        st.info("No mapped region rows were available in the selected date range.")
    else:
        st.dataframe(
            region_focus.head(12)[
                [
                    "reporting_region",
                    "area_macro",
                    "attack_rows",
                    "launched_total_allocated",
                    "launched_total_exploded",
                    "allocated_share_pct",
                ]
            ].rename(
                columns={
                    "reporting_region": "Reporting region",
                    "area_macro": "Macro area",
                    "attack_rows": "Strikes",
                    "launched_total_allocated": "Allocated launched total",
                    "launched_total_exploded": "Exploded launched total",
                    "allocated_share_pct": "Allocated share %",
                }
            ),
            use_container_width=True,
            hide_index=True,
        )
