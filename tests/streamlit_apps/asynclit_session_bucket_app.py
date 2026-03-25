"""Verify ``session_tasks`` returns the same mapping across Streamlit reruns."""

from __future__ import annotations

import streamlit as st

import asynclit


bucket = asynclit.session_tasks(st.session_state, key="bucket_test")
if "phase" not in bucket:
    bucket["phase"] = 1
    st.markdown("first")
else:
    st.markdown("second")
