from __future__ import annotations

import plotly.express as px
import streamlit as st

from dashboard.data import ensure_gold_database, query


st.set_page_config(page_title="Areas", layout="wide")
st.title("Areas")
st.caption("Target macro areas, directional summaries, and centroid maps.")

# Stop early if the pipeline has not built the gold database yet.
ensure_gold_database()

# Load area-level marts from the gold layer.
area_macros = query("SELECT * FROM vw_dashboard_area_macros")
directional = query("SELECT * FROM vw_dashboard_directional_macros")
region_map = query("SELECT * FROM vw_dashboard_region_map")

st.subheader("Area Macro Summary")

# Log scale is helpful because nationwide rows are much larger than most specific regions.
use_log = st.checkbox("Use log scale for launched totals", value=True)
fig = px.bar(
    area_macros,
    x="area_macro",
    y="launched_total",
    text="attack_rows",
    color="launched_total",
    color_continuous_scale=["#2b0a0a", "#5e1111", "#962020", "#d73a31"],
    title="Launched total by area macro",
)
fig.update_layout(xaxis_title="Area macro", yaxis_title="Launched total")
if use_log:
    fig.update_yaxes(type="log")
st.plotly_chart(fig, use_container_width=True)

st.subheader("Directional Macro Map")

# Macro centroids give a coarse directional view, not exact strike locations.
fig = px.scatter_geo(
    directional,
    lat="lat",
    lon="lon",
    text="area_macro",
    size="attack_rows",
    size_max=48,
    color="launched_total",
    hover_name="area_macro",
    hover_data={
        "attack_rows": True,
        "active_days": True,
        "launched_total": True,
        "destroyed_total": True,
        "lat": False,
        "lon": False,
    },
    color_continuous_scale=["#220707", "#5a1010", "#9e1e1e", "#ff7043"],
    projection="mercator",
    scope="europe",
    title="Directional macro target map",
)
fig.update_traces(
    marker=dict(line=dict(color="black", width=1.0), opacity=0.9, sizemin=14),
    textposition="top center",
)
fig.update_geos(
    center={"lat": 48.8, "lon": 31.5},
    lataxis_range=[44, 53],
    lonaxis_range=[22, 41],
    showcountries=True,
    countrycolor="rgb(90, 90, 90)",
    showland=True,
    landcolor="rgb(239, 236, 230)",
    showocean=True,
    oceancolor="rgb(222, 228, 236)",
)
st.plotly_chart(fig, use_container_width=True)

st.subheader("Specific Region Map")

# Drop rows without coordinates because Plotly cannot place them on the map.
mapped_regions = region_map[region_map["lat"].notna()].copy()

# Label only the busiest regions to keep the map readable.
mapped_regions["label"] = ""
if not mapped_regions.empty:
    label_threshold = mapped_regions["attack_rows"].quantile(0.85)
    mapped_regions.loc[mapped_regions["attack_rows"] >= label_threshold, "label"] = mapped_regions["area_region"]

# Region totals come from the exploded region table, so multi-area attack rows can contribute to several points.
fig = px.scatter_geo(
    mapped_regions,
    lat="lat",
    lon="lon",
    text="label",
    size="attack_rows",
    size_max=50,
    color="launched_total_exploded",
    hover_name="area_region",
    hover_data={
        "attack_rows": True,
        "active_days": True,
        "launched_total_exploded": True,
        "area_kind": True,
        "lat": False,
        "lon": False,
        "label": False,
    },
    color_continuous_scale=["#220707", "#5a1010", "#9e1e1e", "#ff7043"],
    projection="mercator",
    scope="europe",
    title="Region activity map",
)
fig.update_traces(
    marker=dict(line=dict(color="black", width=0.9), opacity=0.9, sizemin=12),
    textposition="top center",
)
fig.update_geos(
    center={"lat": 48.8, "lon": 31.5},
    lataxis_range=[44, 53],
    lonaxis_range=[22, 41],
    showcountries=True,
    countrycolor="rgb(90, 90, 90)",
    showland=True,
    landcolor="rgb(239, 236, 230)",
    showocean=True,
    oceancolor="rgb(222, 228, 236)",
)
st.plotly_chart(fig, use_container_width=True)

# Explain the most important caveat of the exploded region view directly in the UI.
st.info(
    "Region totals come from an exploded area table. If one attack row names several areas, that row appears once per area."
)
