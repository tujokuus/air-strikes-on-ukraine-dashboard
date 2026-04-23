from __future__ import annotations

import plotly.express as px
import streamlit as st

from dashboard.data import ensure_gold_database, query


st.title("Weapons")
st.caption("Weapon model and type summaries from the gold DuckDB layer.")

# Stop early if the pipeline has not built the gold database yet.
ensure_gold_database()

# These views are pre-aggregated in the gold layer for fast dashboard loading.
models = query("SELECT * FROM vw_dashboard_weapon_models")
types = query("SELECT * FROM vw_dashboard_weapon_types")

# Build filter choices from the data so new weapon categories appear automatically.
categories = sorted(models["weapon_category"].dropna().unique().tolist())
selected_categories = st.multiselect(
    "Weapon categories",
    categories,
    default=categories,
)
top_n = st.slider("Top weapon models", min_value=5, max_value=30, value=15, step=5)

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

