from __future__ import annotations

from datetime import date

import pandas as pd
import streamlit as st

from dashboard.data import query


DATE_RANGE_STATE_KEY = "selected_event_date_range"
DATE_RANGE_WIDGET_KEY = "selected_event_date_range_widget"


def _to_date(value: object) -> date | None:
    """Convert a pandas or Python date-like value into a plain date."""
    if pd.isna(value):
        return None
    return pd.Timestamp(value).date()


def get_available_date_range() -> tuple[date, date]:
    """Return the full event-date range available in the dashboard data."""
    bounds = query(
        """
        SELECT
            MIN(event_date) AS min_date,
            MAX(event_date) AS max_date
        FROM vw_dashboard_daily_activity
        """
    ).iloc[0]

    min_date = _to_date(bounds["min_date"])
    max_date = _to_date(bounds["max_date"])
    if min_date is None or max_date is None:
        today = date.today()
        return today, today
    return min_date, max_date


def get_selected_date_range() -> tuple[date, date]:
    """Return the selected global date range, or the full range when unset."""
    selected = st.session_state.get(DATE_RANGE_STATE_KEY)
    if selected is None:
        return get_available_date_range()
    return selected


def render_global_date_filter() -> tuple[date, date]:
    """Render the shared sidebar date filter and store the result in session state."""
    min_date, max_date = get_available_date_range()
    current_start, current_end = get_selected_date_range()

    current_start = max(min_date, min(current_start, max_date))
    current_end = min(max_date, max(current_end, min_date))

    st.sidebar.markdown("## Filters")
    selected_range = st.sidebar.date_input(
        "Event date range",
        value=(current_start, current_end),
        min_value=min_date,
        max_value=max_date,
        key=DATE_RANGE_WIDGET_KEY,
    )

    if isinstance(selected_range, tuple) and len(selected_range) == 2:
        start_date, end_date = selected_range
    elif isinstance(selected_range, list) and len(selected_range) == 2:
        start_date, end_date = selected_range[0], selected_range[1]
    else:
        start_date, end_date = min_date, max_date

    if start_date > end_date:
        start_date, end_date = end_date, start_date

    start_date = max(min_date, start_date)
    end_date = min(max_date, end_date)
    selected = (start_date, end_date)

    st.session_state[DATE_RANGE_STATE_KEY] = selected
    st.sidebar.caption(f"Available data: {min_date:%d.%m.%Y} - {max_date:%d.%m.%Y}")
    return selected
