"""
asynclet: background tasks for rerun-driven UIs.

asynclet provides a small polling-friendly API for running sync/async callables on a
dedicated background asyncio event loop. It is designed for Streamlit-style apps
where the main script reruns frequently and must not block.
"""

from __future__ import annotations

import warnings

from asynclit import (
    RetryPolicy,
    ScheduledTask,
    SchedulerUnavailable,
    Task,
    TaskManager,
    TaskStatus,
    get_default_manager,
    get_default_scheduler,
    run,
    schedule_cron,
    schedule_interval,
    shutdown_scheduler,
    start_scheduler,
)
from asynclet.session import session_tasks as session_tasks  # noqa: E402,F401

warnings.warn(
    "`asynclet` has been renamed to `asynclit`. Please update imports to `asynclit`.",
    DeprecationWarning,
    stacklevel=2,
)

from asynclit import __version__ as __version__  # noqa: E402

__all__ = [
    "Task",
    "TaskStatus",
    "TaskManager",
    "get_default_manager",
    "run",
    "RetryPolicy",
    "SchedulerUnavailable",
    "ScheduledTask",
    "get_default_scheduler",
    "start_scheduler",
    "shutdown_scheduler",
    "schedule_interval",
    "schedule_cron",
    "session_tasks",
]
