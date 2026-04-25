from __future__ import annotations

import pandas as pd
import plotly.express as px
import streamlit as st

from dashboard.date_queries import (
    get_filtered_weapon_models,
    get_filtered_weapon_types,
    get_weapon_category_over_time,
)
from dashboard.filters import get_selected_date_range


def get_time_bucket_label(start_date, end_date) -> tuple[str, str]:
    period_days = (end_date - start_date).days + 1
    if period_days <= 60:
        return "day", "Day"
    if period_days <= 240:
        return "week", "Week starting"
    return "month", "Month"


def bucket_time_series(frame: pd.DataFrame, bucket: str, group_columns: list[str]) -> pd.DataFrame:
    if frame.empty:
        return frame.copy()

    series = frame.copy()
    event_dates = pd.to_datetime(series["event_date"])
    if bucket == "month":
        series["period_start"] = event_dates.dt.to_period("M").dt.to_timestamp()
    elif bucket == "week":
        series["period_start"] = event_dates - pd.to_timedelta(event_dates.dt.weekday, unit="D")
    else:
        series["period_start"] = event_dates.dt.normalize()

    value_columns = [column for column in ["attack_rows", "launched_total", "destroyed_total"] if column in series]
    aggregated = (
        series.groupby(["period_start", *group_columns], as_index=False)[value_columns]
        .sum()
        .sort_values(["period_start", *group_columns])
    )
    return aggregated


st.title("Weapons")
st.caption("Weapon model and type summaries from the gold DuckDB layer.")
selected_start, selected_end = get_selected_date_range()
st.caption(f"Selected range: {selected_start:%d.%m.%Y} - {selected_end:%d.%m.%Y}")

models = get_filtered_weapon_models(selected_start, selected_end)
types = get_filtered_weapon_types(selected_start, selected_end)
category_history = get_weapon_category_over_time(selected_start, selected_end)

if models.empty or types.empty:
    st.info("No weapon data was found in the selected date range.")
    st.stop()

# Build filter choices from the data so new weapon categories appear automatically.
categories = sorted(models["weapon_category"].dropna().unique().tolist())
selected_categories = st.multiselect(
    "Weapon categories",
    categories,
    default=categories,
)
top_n = st.slider("Top weapon models", min_value=5, max_value=30, value=15, step=5)

if not selected_categories:
    st.info("Select at least one weapon category to see the charts.")
    st.stop()

# Assign colors from the full category list so filtering does not reshuffle them.
weapon_category_palette = ["#2d6a4f", "#9e1e1e", "#3a3a3a", "#b7791f", "#4a5568"]
weapon_category_colors = {
    category: weapon_category_palette[index % len(weapon_category_palette)]
    for index, category in enumerate(categories)
}

weapon_type_examples = {
    "loitering munition": "Kamikaze drone: waits or circles before diving into the target.",
    "reconnaissance": "Unarmed drone used mainly for observation and locating targets.",
    "reconnaissance and armed": "Drone that can both scout and carry or drop weapons.",
    "multirole ISTAR": "Drone used for intelligence, surveillance, target acquisition, and reconnaissance.",
    "land-attack": "Cruise missile designed to strike targets on land.",
    "air-launched": "Missile released from an aircraft before flying to the target.",
    "air-to-surface": "Weapon fired from the air against targets on the ground or at sea.",
    "anti-ship": "Missile designed primarily to hit ships.",
    "anti-radiation": "Missile designed to detect and home in on an enemy radio emission source.",
    "solid-fueled, tactical": "Shorter-range ballistic missile using solid fuel, usually for battlefield or regional targets.",
    "TV-guided, tactical": "Tactical missile guided by a television or optical seeker.",
    "anti-ballistic missile": "Missile intended to intercept incoming ballistic missiles.",
    "santi-ballistic missile": "Likely anti-ballistic missile; source label appears misspelled.",
    "air-launched, air-to-surface, anti-ship, land-attack": (
        "Aircraft-launched cruise missile usable against ships or land targets."
    ),
    "anti-ship, hypersonic, submarine-launched, land-attack, scramjet-powered, nuclear-capable": (
        "Advanced submarine-launched hypersonic cruise missile family with anti-ship and land-attack roles."
    ),
    "Unknown type": "The source/reference data does not provide a more specific type.",
    "Mixed/Various": "The model group contains more than one weapon type.",
}

# Apply the same category filter to both model-level and type-level summaries.
filtered_models = models[models["weapon_category"].isin(selected_categories)].copy()
filtered_types = types[types["weapon_category"].isin(selected_categories)].copy()
filtered_category_history = category_history[category_history["weapon_category"].isin(selected_categories)].copy()

time_bucket, period_label = get_time_bucket_label(selected_start, selected_end)

st.subheader("Top Weapon Models")

# Keep only the selected number of models, then sort for a readable horizontal bar chart.
top_models = filtered_models.head(top_n).sort_values("launched_total", ascending=True)
fig = px.bar(
    top_models,
    x="launched_total",
    y="weapon_model",
    color="weapon_category",
    orientation="h",
    hover_data=["weapon_type", "attack_rows", "active_days", "reference_coverage_pct"],
    color_discrete_map=weapon_category_colors,
    title="Launched total by weapon model",
)
fig.update_layout(xaxis_title="Launched total", yaxis_title="Weapon model", legend_title_text="")
st.plotly_chart(fig, use_container_width=True)

st.subheader("Weapon Share Over Time")
category_share_frame = bucket_time_series(
    filtered_category_history,
    time_bucket,
    ["weapon_category"],
)
if category_share_frame.empty:
    st.info("No weapon-category history was found in the selected range.")
else:
    category_share_frame["launched_share_pct"] = (
        100.0
        * category_share_frame["launched_total"]
        / category_share_frame.groupby("period_start")["launched_total"].transform("sum").replace({0: pd.NA})
    ).fillna(0.0).round(2)
    share_fig = px.area(
        category_share_frame,
        x="period_start",
        y="launched_share_pct",
        color="weapon_category",
        color_discrete_map=weapon_category_colors,
        hover_data=["launched_total", "destroyed_total", "attack_rows"],
        title=f"Share of launched total by weapon category over time ({period_label.lower()} aggregation)",
    )
    share_fig.update_layout(
        xaxis_title=period_label,
        yaxis_title="Launched share %",
        legend_title_text="",
    )
    st.plotly_chart(share_fig, use_container_width=True)

st.subheader("Weapon Type Summary")

# This chart groups models into broader weapon types from the reference data.
fig = px.bar(
    filtered_types.sort_values("launched_total", ascending=True),
    x="launched_total",
    y="weapon_type",
    color="weapon_category",
    orientation="h",
    hover_data=["attack_rows", "active_days", "launched_share_pct"],
    color_discrete_map=weapon_category_colors,
    title="Launched total by weapon type",
)
fig.update_layout(xaxis_title="Launched total", yaxis_title="Weapon type", legend_title_text="")
st.plotly_chart(fig, use_container_width=True)

visible_weapon_types = filtered_types["weapon_type"].dropna().drop_duplicates().sort_values()
type_guide = [
    {
        "Weapon type": weapon_type,
        "Plain-language meaning": weapon_type_examples.get(
            weapon_type,
            "No plain-language note added yet.",
        ),
    }
    for weapon_type in visible_weapon_types
]

if type_guide:
    st.markdown("**Weapon type guide**")
    st.dataframe(type_guide, use_container_width=True, hide_index=True)

