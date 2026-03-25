"""
APScheduler-backed scheduling helpers (optional extra).

Install:
    `pip install 'asynclit[scheduler]'`

The scheduler is bound to asynclit's dedicated worker loop so scheduled jobs submit
tasks on the same background loop used by `asynclit.run`.
"""

from __future__ import annotations

import threading
from dataclasses import dataclass
from typing import TYPE_CHECKING, Optional, Type

from asynclit.manager import TaskManager, get_default_manager
from asynclit.task import Task
from asynclit.worker import get_worker_loop

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
    """Raised when scheduling helpers are used without APScheduler installed."""

    pass


def _require_scheduler() -> Type["_AsyncIOScheduler"]:
    if AsyncIOScheduler is None:
        raise SchedulerUnavailable(
            "APScheduler is not installed. Install with: pip install 'asynclit[scheduler]'"
        )
    return AsyncIOScheduler


@dataclass(frozen=True)
class ScheduledTask:
    """
    Metadata returned by scheduling helpers.

    Attributes:
        job_id: APScheduler job id.
        latest_task_key: Optional manager alias key (`global:{name}`) when `latest_task_name` is used.
    """

    job_id: str
    latest_task_key: Optional[str] = None


_default_scheduler: Optional["_AsyncIOScheduler"] = None
_default_scheduler_lock = threading.Lock()


def get_default_scheduler() -> "_AsyncIOScheduler":
    """
    Return a process-wide AsyncIOScheduler bound to the asynclit worker loop.

    Requires installing the optional extra: ``asynclit[scheduler]``.
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
    """
    Start the scheduler (on the worker loop thread) and return it.

    Args:
        scheduler: Scheduler instance to start (defaults to the singleton).
    """
    sch = scheduler or get_default_scheduler()
    if not sch.running:
        loop = get_worker_loop()
        started = threading.Event()
        err: list[BaseException] = []

        def _start() -> None:
            try:
                sch.start()
            except BaseException as exc:  # pragma: no cover - hard to hit without fakes
                err.append(exc)
            finally:
                started.set()

        loop.call_soon_threadsafe(_start)
        if not started.wait(timeout=5.0):
            raise RuntimeError("asynclit scheduler failed to start")
        if err:
            raise err[0]
    return sch


def shutdown_scheduler(
    scheduler: Optional["_AsyncIOScheduler"] = None, *, wait: bool = False
) -> None:
    """
    Shutdown the scheduler (on the worker loop thread).

    Args:
        scheduler: Scheduler instance to shutdown (defaults to the singleton if created).
        wait: Whether to wait for running jobs (passed to APScheduler).
    """
    global _default_scheduler
    sch = scheduler or _default_scheduler
    if sch is None:
        return
    if sch.running:
        loop = get_worker_loop()
        done = threading.Event()
        err: list[BaseException] = []

        def _shutdown() -> None:
            try:
                sch.shutdown(wait=wait)
            except BaseException as exc:  # pragma: no cover - hard to hit without fakes
                err.append(exc)
            finally:
                done.set()

        loop.call_soon_threadsafe(_shutdown)
        done.wait(timeout=5.0)
        if err:
            raise err[0]
    if scheduler is None and sch is _default_scheduler:
        _default_scheduler = None


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
    Schedule periodic execution of `func` using an interval trigger.

    Each tick submits an asynclit `Task` via the provided manager.

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
    Schedule periodic execution of `func` using a cron expression.

    The cron expression uses APScheduler's `CronTrigger.from_crontab` format.
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
