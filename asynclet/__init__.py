"""Async task layer for Streamlit: background execution, polling, progress, cancellation."""

from asynclet.manager import TaskManager, get_default_manager, run
from asynclet.retry import RetryPolicy
from asynclet.scheduler import (
    SchedulerUnavailable,
    ScheduledTask,
    get_default_scheduler,
    schedule_cron,
    schedule_interval,
    shutdown_scheduler,
    start_scheduler,
)
from asynclet.session import session_tasks
from asynclet.task import Task, TaskStatus

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

__version__ = "0.2.0"
