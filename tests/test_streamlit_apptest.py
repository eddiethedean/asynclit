"""
Integration tests using Streamlit's headless ``AppTest`` API.

Background work is scheduled on asynclit's worker thread. ``AppTest.run()`` returns as
soon as the script finishes, so rapid back-to-back runs may observe ``wait`` forever unless
the test allows a little wall time between runs (mirrors a human delay between reruns) or
the app cooperates with a short in-script pause (see ``asynclet_poll_cooperative_app``).
"""

from __future__ import annotations

import time
from pathlib import Path

import pytest

pytest.importorskip("streamlit.testing.v1")

from streamlit.testing.v1 import AppTest

APPS_DIR = Path(__file__).resolve().parent / "streamlit_apps"


def _markdown_values(at: AppTest) -> list[str]:
    return [m.value for m in at.markdown]


def test_apptest_poll_app_eventually_ready_after_wall_clock_gap():
    """Two reruns with real time between them so the worker can finish."""
    path = APPS_DIR / "asynclet_poll_app.py"
    at = AppTest.from_file(str(path))
    at.run(timeout=60)
    assert not at.exception
    assert _markdown_values(at) == ["wait"]
    time.sleep(0.35)
    at.run(timeout=60)
    assert not at.exception
    assert _markdown_values(at) == ["ready:138"]


def test_apptest_poll_cooperative_single_run_completes():
    """One rerun: script yields wall time so ``task.done`` is true before exit."""
    path = APPS_DIR / "asynclet_poll_cooperative_app.py"
    at = AppTest.from_file(str(path))
    at.run(timeout=60)
    assert not at.exception
    assert _markdown_values(at) == ["ready:42"]


def test_apptest_progress_app_emits_ticks_and_done():
    path = APPS_DIR / "asynclet_progress_app.py"
    at = AppTest.from_file(str(path))
    collected: list[str] = []
    for _ in range(40):
        at.run(timeout=60)
        assert not at.exception
        collected.extend(_markdown_values(at))
        if any(v.startswith("done:") for v in collected):
            break
        time.sleep(0.06)
    assert any(v == "done:4" for v in collected)
    assert any(v.startswith("tick:") for v in collected)


def test_apptest_session_tasks_bucket_persists_across_runs():
    path = APPS_DIR / "asynclet_session_bucket_app.py"
    at = AppTest.from_file(str(path))
    at.run(timeout=60)
    assert not at.exception
    assert _markdown_values(at) == ["first"]
    at.run(timeout=60)
    assert not at.exception
    assert _markdown_values(at) == ["second"]
