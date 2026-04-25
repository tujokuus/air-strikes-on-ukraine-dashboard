from __future__ import annotations

import streamlit as st

from dashboard.filters import render_global_date_filter


st.set_page_config(
    page_title="Test Dashboard",
    page_icon="",
    layout="wide",
)

pages = {
    "Air Strikes in Ukraine Analytics": [
        st.Page("pages/overview.py", title="Overview"),
        st.Page("pages/1_Weapons.py", title="Weapons"),
        st.Page("pages/2_Areas.py", title="Areas"),
        st.Page("pages/3_Analysis.py", title="Analysis"),
    ],
}

render_global_date_filter()

navigation = st.navigation(pages)
navigation.run()
