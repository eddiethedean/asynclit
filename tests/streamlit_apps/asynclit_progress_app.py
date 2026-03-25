"""
Streamlit app: asynclit progress streaming (Janus) across reruns.

Run manually: ``streamlit run tests/streamlit_apps/asynclet_progress_app.py``
"""

from __future__ import annotations

import streamlit as st

import asynclit


async def emit(queue, steps: int) -> int:
    for i in range(steps):
        await queue.async_q.put(i)
    return steps


tasks = asynclit.session_tasks(st.session_state, key="asynclit_progress_demo")
if "job" not in tasks:
    tasks["job"] = asynclit.run(emit, 4)

task = tasks["job"]
for x in task.progress:
    st.markdown(f"tick:{x}")
if task.done:
    st.markdown(f"done:{task.result}")
else:
    st.markdown("started")
