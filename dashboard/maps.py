from __future__ import annotations

import pydeck as pdk
import streamlit as st


def pick_available_column(frame, preferred: str, fallback: str) -> str:
    """Return the preferred column when available, otherwise use a safe fallback."""
    return preferred if preferred in frame.columns else fallback


def interpolate_rgba(start_color: list[int], end_color: list[int], ratio: float) -> list[int]:
    """Blend between two RGBA colors with a clamped linear ratio."""
    ratio = max(0.0, min(1.0, float(ratio)))
    return [
        round(start_channel + (end_channel - start_channel) * ratio)
        for start_channel, end_channel in zip(start_color, end_color)
    ]


def add_map_marker_columns(
    frame,
    color_value_column: str,
    size_value_column: str,
    color_scheme: str = "red",
):
    """Add pydeck-compatible marker size and color columns."""
    map_frame = frame.copy()

    max_size_value = map_frame[size_value_column].max()
    if max_size_value and max_size_value > 0:
        size_ratio = (map_frame[size_value_column] / max_size_value).pow(0.5)
        map_frame["marker_size"] = (15_000 + size_ratio * 85_000).round(0)
    else:
        map_frame["marker_size"] = 24_000

    max_color_value = map_frame[color_value_column].max()

    def marker_color(value):
        color_ranges = {
            "red": ([255, 228, 230, 150], [127, 0, 0, 190]),
            "green": ([220, 252, 231, 150], [22, 101, 52, 190]),
        }
        start_color, end_color = color_ranges[color_scheme]

        if not max_color_value or max_color_value <= 0:
            return end_color

        ratio = value / max_color_value
        return interpolate_rgba(start_color, end_color, ratio)

    map_frame["marker_color"] = map_frame[color_value_column].apply(marker_color)
    return map_frame


def render_map_legend(metric_label: str, size_label: str, color_scheme: str) -> None:
    """Render a compact visual legend for map marker color and size."""
    if color_scheme == "green":
        gradient = (
            "linear-gradient(90deg, #dcfce7 0%, #b7e8c1 20%, #86d19a 40%, "
            "#56ba73 60%, #2f944f 80%, #166534 100%)"
        )
        accent = "#166534"
        border = "#bbf7d0"
        background = "#f8fffb"
    else:
        gradient = (
            "linear-gradient(90deg, #ffe4e6 0%, #ffc2c7 20%, #ff9494 40%, "
            "#f85b5b 60%, #cc2020 80%, #7f0000 100%)"
        )
        accent = "#991b1b"
        border = "#fecdd3"
        background = "#fff8f8"

    st.markdown(
        f"""
        <div style="
            border: 1px solid {border};
            border-radius: 8px;
            padding: 0.9rem;
            margin-top: 0.25rem;
            background: {background};
            box-shadow: 0 1px 2px rgba(15, 23, 42, 0.05);
        ">
            <div style="font-size: 0.82rem; font-weight: 700; letter-spacing: 0.04em; text-transform: uppercase; color: {accent}; margin-bottom: 0.7rem;">
                Map guide
            </div>
            <div style="font-weight: 600; color: #111827; margin-bottom: 0.38rem;">Color intensity</div>
            <div style="
                height: 12px;
                border-radius: 999px;
                background: {gradient};
                border: 1px solid rgba(17, 24, 39, 0.08);
                margin-bottom: 0.3rem;
            "></div>
            <div style="
                display: flex;
                justify-content: space-between;
                font-size: 0.84rem;
                color: #4b5563;
                margin-bottom: 0.8rem;
            ">
                <span>Lower {metric_label.lower()}</span>
                <span>Higher {metric_label.lower()}</span>
            </div>
            <div style="font-weight: 600; color: #111827; margin-bottom: 0.45rem;">Marker size</div>
            <div style="display: flex; align-items: flex-end; gap: 0.65rem; margin-bottom: 0.35rem;">
                <div style="
                    width: 12px;
                    height: 12px;
                    border-radius: 999px;
                    background: rgba(107, 114, 128, 0.5);
                    border: 1px solid rgba(75, 85, 99, 0.35);
                "></div>
                <div style="
                    width: 22px;
                    height: 22px;
                    border-radius: 999px;
                    background: rgba(107, 114, 128, 0.42);
                    border: 1px solid rgba(75, 85, 99, 0.35);
                "></div>
                <div style="
                    width: 34px;
                    height: 34px;
                    border-radius: 999px;
                    background: rgba(107, 114, 128, 0.34);
                    border: 1px solid rgba(75, 85, 99, 0.35);
                "></div>
            </div>
            <div style="font-size: 0.84rem; color: #4b5563; margin-bottom: 0.8rem;">
                Larger circles mean higher {size_label.lower()}.
            </div>
            <div style="
                font-size: 0.82rem;
                color: #6b7280;
                line-height: 1.4;
                padding-top: 0.7rem;
                border-top: 1px solid rgba(148, 163, 184, 0.22);
            ">
                Points use approximate centroids, not exact strike coordinates or boundaries.
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_point_map(frame, tooltip_text: str, height: int) -> None:
    """Render a pydeck point map with hover tooltip support."""
    point_layer = pdk.Layer(
        "ScatterplotLayer",
        data=frame,
        get_position="[lon, lat]",
        get_radius="marker_size",
        get_fill_color="marker_color",
        pickable=True,
        auto_highlight=True,
    )
    view_state = pdk.ViewState(
        latitude=48.9,
        longitude=31.5,
        zoom=5.1,
        pitch=0,
    )
    deck = pdk.Deck(
        map_style=None,
        initial_view_state=view_state,
        layers=[point_layer],
        tooltip={"text": tooltip_text},
    )
    st.pydeck_chart(deck, width="stretch", height=height)
