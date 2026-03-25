"""
Optional APScheduler integration — install with ``pip install 'asynclet[scheduler]'``.

To drive timers on the same loop as asynclet tasks, obtain the loop with
``asynclet.worker.get_worker_loop()`` and configure ``AsyncIOScheduler`` with that loop
(see APScheduler docs for ``AsyncIOScheduler(event_loop=...)``).
"""

from __future__ import annotations

import threading
from dataclasses import dataclass
from typing import TYPE_CHECKING, Optional, Type

from asynclet.manager import TaskManager, get_default_manager
from asynclet.task import Task
from asynclet.worker import get_worker_loop

__all__: list[str] = []

if TYPE_CHECKING:  # pragma: no cover
    from apscheduler.schedulers.asyncio import AsyncIOScheduler as _AsyncIOScheduler
    from apscheduler.triggers.cron import CronTrigger
    from apscheduler.triggers.interval import IntervalTrigger

AsyncIOScheduler: Optional[Type["_AsyncIOScheduler"]]

try:  # pragma: no branch - optional dependency
    from apscheduler.schedulers.asyncio import (
        AsyncIOScheduler as _RuntimeAsyncIOScheduler,
    )
    from apscheduler.triggers.cron import CronTrigger
    from apscheduler.triggers.interval import IntervalTrigger

    AsyncIOScheduler = _RuntimeAsyncIOScheduler
    __all__.append("AsyncIOScheduler")
except ImportError:
    AsyncIOScheduler = None


class SchedulerUnavailable(RuntimeError):
    pass


def _require_scheduler() -> Type["_AsyncIOScheduler"]:
    if AsyncIOScheduler is None:
        raise SchedulerUnavailable(
            "APScheduler is not installed. Install with: pip install 'asynclet[scheduler]'"
        )
    return AsyncIOScheduler


@dataclass(frozen=True)
class ScheduledTask:
    """Returned by scheduling helpers to identify the job and latest task alias."""

    job_id: str
    latest_task_key: Optional[str] = None


_default_scheduler: Optional["_AsyncIOScheduler"] = None
_default_scheduler_lock = threading.Lock()


def get_default_scheduler() -> "_AsyncIOScheduler":
    """
    Return a process-wide AsyncIOScheduler bound to the asynclet worker loop.

    Requires installing the optional extra: ``asynclet[scheduler]``.
    """
    global _default_scheduler
    cls = _require_scheduler()
    with _default_scheduler_lock:
        if _default_scheduler is None:
            loop = get_worker_loop()
            _default_scheduler = cls(event_loop=loop)
        return _default_scheduler


def start_scheduler(
    scheduler: Optional["_AsyncIOScheduler"] = None,
) -> "_AsyncIOScheduler":
    sch = scheduler or get_default_scheduler()
    if not sch.running:
        loop = get_worker_loop()
        started = threading.Event()

        def _start() -> None:
            try:
                sch.start()
            finally:
                started.set()

        loop.call_soon_threadsafe(_start)
        if not started.wait(timeout=5.0):
            raise RuntimeError("asynclet scheduler failed to start")
    return sch


def shutdown_scheduler(
    scheduler: Optional["_AsyncIOScheduler"] = None, *, wait: bool = False
) -> None:
    sch = scheduler or _default_scheduler
    if sch is None:
        return
    if sch.running:
        loop = get_worker_loop()
        done = threading.Event()

        def _shutdown() -> None:
            try:
                sch.shutdown(wait=wait)
            finally:
                done.set()

        loop.call_soon_threadsafe(_shutdown)
        done.wait(timeout=5.0)


def schedule_interval(
    func,
    *,
    seconds: float,
    args: tuple = (),
    kwargs: Optional[dict] = None,
    manager: Optional[TaskManager] = None,
    scheduler: Optional["_AsyncIOScheduler"] = None,
    job_id: Optional[str] = None,
    replace_existing: bool = True,
    latest_task_name: Optional[str] = None,
) -> ScheduledTask:
    """
    Schedule periodic execution of ``func``. Each tick submits an asynclet Task.

    If ``latest_task_name`` is set, the latest Task is stored as a manager global alias
    under key ``global:{latest_task_name}``.
    """
    sch = start_scheduler(scheduler)
    m = manager or get_default_manager()
    kw = kwargs or {}
    alias_key = f"global:{latest_task_name}" if latest_task_name else None

    def _tick() -> None:
        task: Task = m.submit(func, *args, **kw)
        if latest_task_name is not None:
            m.register_global(task, latest_task_name)

    trigger = IntervalTrigger(seconds=seconds)
    job = sch.add_job(
        _tick, trigger=trigger, id=job_id, replace_existing=replace_existing
    )
    return ScheduledTask(job_id=job.id, latest_task_key=alias_key)


def schedule_cron(
    func,
    *,
    cron: str,
    args: tuple = (),
    kwargs: Optional[dict] = None,
    manager: Optional[TaskManager] = None,
    scheduler: Optional["_AsyncIOScheduler"] = None,
    job_id: Optional[str] = None,
    replace_existing: bool = True,
    latest_task_name: Optional[str] = None,
) -> ScheduledTask:
    """
    Schedule execution of ``func`` using a cron expression.

    The cron expression uses APScheduler's CronTrigger.from_crontab format.
    """
    sch = start_scheduler(scheduler)
    m = manager or get_default_manager()
    kw = kwargs or {}
    alias_key = f"global:{latest_task_name}" if latest_task_name else None

    def _tick() -> None:
        task: Task = m.submit(func, *args, **kw)
        if latest_task_name is not None:
            m.register_global(task, latest_task_name)

    trigger = CronTrigger.from_crontab(cron)
    job = sch.add_job(
        _tick, trigger=trigger, id=job_id, replace_existing=replace_existing
    )
    return ScheduledTask(job_id=job.id, latest_task_key=alias_key)
