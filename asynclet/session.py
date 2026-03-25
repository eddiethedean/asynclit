"""
Session helpers for rerun-driven UIs (no hard dependency on Streamlit).

Pass `st.session_state` (or any mapping-like object) to store tasks across reruns.
"""

from __future__ import annotations

from typing import Any, Dict, cast


def session_tasks(
    session_state: Any,
    key: str = "asynclet_tasks",
) -> Dict[str, Any]:
    """
    Return a task registry dict stored on `session_state[key]`.

    This is a convenience for Streamlit apps that want a stable dict for named tasks.

    Args:
        session_state: `st.session_state` or a compatible mapping-like object.
        key: Storage key used within the session state.

    Returns:
        A mutable dict that persists across reruns.
    """
    if key not in session_state:
        session_state[key] = {}
    return cast(Dict[str, Any], session_state[key])
