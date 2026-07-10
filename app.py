"""Streamlit entry: multi-page navigation."""

from __future__ import annotations

import streamlit as st

st.set_page_config(page_title="Finance Tracker", layout="wide")

pdf_page = st.Page("pages/pdf_to_csv.py", title="PDF to CSV", default=True)
finance_page = st.Page("pages/finance_tracker.py", title="Finance Tracker")

pg = st.navigation([pdf_page, finance_page])
pg.run()
