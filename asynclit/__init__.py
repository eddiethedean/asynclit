"""
asynclit: background tasks for rerun-driven UIs.

asynclit provides a small polling-friendly API for running sync/async callables on a
dedicated background asyncio event loop. It is designed for Streamlit-style apps
where the main script reruns frequently and must not block.
"""

from asynclit.manager import TaskManager, get_default_manager, run
from asynclit.retry import RetryPolicy
from asynclit.scheduler import (
    SchedulerUnavailable,
    ScheduledTask,
    get_default_scheduler,
    schedule_cron,
    schedule_interval,
    shutdown_scheduler,
    start_scheduler,
)
from asynclit.session import session_tasks
from asynclit.task import Task, TaskStatus

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

__version__ = "0.2.1"
