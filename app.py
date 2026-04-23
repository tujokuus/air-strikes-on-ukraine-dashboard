from __future__ import annotations

import streamlit as st


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
    ],
}

navigation = st.navigation(pages)
navigation.run()
