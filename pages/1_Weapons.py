from __future__ import annotations

import plotly.express as px
import streamlit as st

from dashboard.data import ensure_gold_database, query


st.set_page_config(page_title="Weapons", layout="wide")
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
    color_discrete_sequence=["#9e1e1e", "#2d6a4f", "#3a3a3a", "#b7791f", "#4a5568"],
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
    color_discrete_sequence=["#9e1e1e", "#2d6a4f", "#3a3a3a", "#b7791f", "#4a5568"],
    title="Launched total by weapon type",
)
fig.update_layout(xaxis_title="Launched total", yaxis_title="Weapon type", legend_title_text="")
st.plotly_chart(fig, use_container_width=True)

st.subheader("Reference Coverage")

# Low coverage rows are useful for spotting weapon names that may need better normalization.
coverage = filtered_models.sort_values(["reference_coverage_pct", "launched_total"], ascending=[True, False]).head(15)
st.dataframe(
    coverage[
        [
            "weapon_model",
            "weapon_category",
            "weapon_type",
            "attack_rows",
            "launched_total",
            "reference_coverage_pct",
            "first_seen",
            "last_seen",
        ]
    ],
    use_container_width=True,
    hide_index=True,
)
