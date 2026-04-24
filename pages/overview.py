from __future__ import annotations

import plotly.express as px
import streamlit as st

from dashboard.data import format_int
from dashboard.date_queries import (
    get_filtered_area_macros,
    get_filtered_daily_activity,
    get_filtered_overview,
    get_filtered_weapon_models,
)
from dashboard.filters import get_selected_date_range


st.title("Air Strikes in Ukraine Analytics")
st.caption("Trends, weapon activity, and target geography.")
selected_start, selected_end = get_selected_date_range()
st.caption(f"Selected range: {selected_start:%d.%m.%Y} - {selected_end:%d.%m.%Y}")

overview = get_filtered_overview(selected_start, selected_end)
daily = get_filtered_daily_activity(selected_start, selected_end)
weapon_models = get_filtered_weapon_models(selected_start, selected_end)
area_macros = get_filtered_area_macros(selected_start, selected_end)

if daily.empty:
    st.info("No events were found in the selected date range.")
    st.stop()

st.subheader("Overview")

st.markdown(
    """
<style>
/* Metricin otsikko (label) */
[data-testid="stMetricLabel"] {
    font-size: 1.8rem;
}

/* Metricin arvo (value) */
[data-testid="stMetricValue"] {
    font-size: 1.8rem;
}
</style>
""",
    unsafe_allow_html=True,
)

# KPI cards give a quick read on dataset coverage and scale.
metric_cols = st.columns(4)
metric_cols[0].metric(
    "Event range",
    f"{overview['first_event_date'].strftime('%d.%m.%Y')} - {overview['last_event_date'].strftime('%d.%m.%Y')}",
)
metric_cols[1].metric("Attacks total", format_int(overview["total_attack_rows"]))
metric_cols[2].metric("Launched total", format_int(overview["total_launched"]))
metric_cols[3].metric("Destroyed total", format_int(overview["total_destroyed"]))

metric_cols = st.columns(5)
metric_cols[0].metric("Weapon models", format_int(overview["distinct_weapon_models"]))
metric_cols[1].metric("Weapon categories", format_int(overview["distinct_weapon_categories"]))
metric_cols[2].metric(
    "Top UAV / Amount launched",
    f"{overview['top_uav_weapon_model_key']}: {format_int(overview['top_uav_launched'])}",
)
metric_cols[3].metric(
    "Top Cruise Missile / Amount launched",
    f"{overview['top_cruise_missile_weapon_model_key']}: {format_int(overview['top_cruise_missile_launched'])}",
)
metric_cols[4].metric(
    "Top Ballistic Missile / Amount launched",
    f"{overview['top_ballistic_missile_weapon_model_key']}: {format_int(overview['top_ballistic_missile_launched'])}",
)

st.subheader("Daily Activity")

# Convert the daily table from wide to long format so one Plotly line can be drawn per metric.
daily_long = daily.melt(
    id_vars="event_date",
    value_vars=["launched_total", "destroyed_total"],
    var_name="metric",
    value_name="value",
)
fig = px.line(
    daily_long,
    x="event_date",
    y="value",
    color="metric",
    color_discrete_map={
        "launched_total": "#9e1e1e",
        "destroyed_total": "#2d6a4f",
    },
    title="Daily launched and destroyed totals",
)
fig.update_layout(xaxis_title="Date", yaxis_title="Count", legend_title_text="")
st.plotly_chart(fig, use_container_width=True)

left, right = st.columns(2)
weapon_category_palette = ["#2d6a4f", "#9e1e1e", "#3a3a3a", "#b7791f", "#4a5568"]
weapon_categories = sorted(weapon_models["weapon_category"].dropna().unique().tolist())
weapon_category_colors = {
    category: weapon_category_palette[index % len(weapon_category_palette)]
    for index, category in enumerate(weapon_categories)
}
area_macros_chart = (
    area_macros.groupby("area_macro", as_index=False)
    .agg(
        attack_rows=("attack_rows", "sum"),
        launched_total=("launched_total", "sum"),
    )
    .sort_values(["launched_total", "attack_rows"], ascending=[False, False])
)
area_total = area_macros_chart["launched_total"].sum()
area_macros_chart["launched_share_pct"] = (
    0.0
    if area_total == 0
    else (100.0 * area_macros_chart["launched_total"] / area_total).round(2)
)

with left:
    st.subheader("Top Weapon Models")

    # Sort ascending before plotting so the largest bar appears at the top of the horizontal chart.
    fig = px.bar(
        weapon_models.head(10).sort_values("launched_total", ascending=True),
        x="launched_total",
        y="weapon_model",
        color="weapon_category",
        orientation="h",
        color_discrete_map=weapon_category_colors,
        title="Launched total by weapon model",
    )
    fig.update_layout(xaxis_title="Launched total", yaxis_title="Weapon model", legend_title_text="")
    st.plotly_chart(fig, use_container_width=True)

with right:
    st.subheader("Target Scope")

    # The color scale highlights the largest target scopes without changing the underlying values.
    fig = px.bar(
        area_macros_chart,
        x="area_macro",
        y="launched_total",
        text="launched_share_pct",
        color="launched_total",
        color_continuous_scale=["#2b0a0a", "#5e1111", "#962020", "#d73a31"],
        title="Launched total by area macro",
    )
    fig.update_layout(xaxis_title="Area macro", yaxis_title="Launched total")
    st.plotly_chart(fig, use_container_width=True)
