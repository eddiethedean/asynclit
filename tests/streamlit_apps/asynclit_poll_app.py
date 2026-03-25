"""
Minimal Streamlit app: session-scoped asynclit task + polling UI.

Run manually: ``streamlit run tests/streamlit_apps/asynclet_poll_app.py``
(from repo root, with the package installed).
"""

from __future__ import annotations

import time

import streamlit as st

import asynclit


def heavy() -> int:
    time.sleep(0.1)
    return 138


tasks = asynclit.session_tasks(st.session_state, key="asynclit_demo")
if "load" not in tasks:
    tasks["load"] = asynclit.run(heavy)

task = tasks["load"]
if task.done:
    st.markdown(f"ready:{task.result}")
else:
    st.markdown("wait")
