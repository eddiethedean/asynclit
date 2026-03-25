"""
Poll pattern with a short in-script pause so a single ``AppTest.run()`` can observe completion.

Useful when tests should not rely on spacing multiple ``run()`` calls in wall clock time.
"""

from __future__ import annotations

import time

import streamlit as st

import asynclit


def work() -> int:
    time.sleep(0.06)
    return 42


tasks = asynclit.session_tasks(st.session_state, key="coop")
if "t" not in tasks:
    tasks["t"] = asynclit.run(work)

task = tasks["t"]
if not task.done:
    time.sleep(0.35)
if task.done:
    st.markdown(f"ready:{task.result}")
else:
    st.markdown("wait")
