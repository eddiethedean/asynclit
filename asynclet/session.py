"""Streamlit session helpers (no hard dependency on Streamlit — pass ``st.session_state``)."""

from __future__ import annotations

from typing import Any, Dict, cast


def session_tasks(
    session_state: Any,
    key: str = "asynclet_tasks",
) -> Dict[str, Any]:
    """
    Return a task registry dict stored on ``session_state[key]``.

    Example::

        import streamlit as st
        import asynclet

        tasks = asynclet.session_tasks(st.session_state)
        tasks["fetch"] = asynclet.run(load_data)
    """
    if key not in session_state:
        session_state[key] = {}
    return cast(Dict[str, Any], session_state[key])
