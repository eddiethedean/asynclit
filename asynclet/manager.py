from __future__ import annotations

import asyncio
import inspect
import queue
import threading
from typing import Any, Callable, Dict, List, Optional, Tuple, TypeVar

from asyncer import asyncify

from asynclet.retry import RetryPolicy
from asynclet.task import Task, TaskStatus, new_task_id
from asynclet.worker import submit_coro

T = TypeVar("T")

_default_manager: Optional["TaskManager"] = None
_default_manager_lock = threading.Lock()


def _bind_progress_queue(
    func: Callable[..., Any],
    queue: Any,
    args: Tuple[Any, ...],
    kwargs: Dict[str, Any],
) -> Tuple[Tuple[Any, ...], Dict[str, Any]]:
    """
    Bind a Janus queue into an async callable's signature.

    If the callable's first parameter is named `queue` or `progress_queue`, the
    queue is passed positionally. Otherwise, it is injected as a keyword argument
    if a matching parameter exists.
    """
    sig = inspect.signature(func)
    params = list(sig.parameters.keys())
    if not params:
        return args, kwargs
    first = params[0]
    if first in ("progress_queue", "queue"):
        kw = {k: v for k, v in kwargs.items() if k not in ("progress_queue", "queue")}
        return (queue,) + args, kw
    if "progress_queue" in sig.parameters:
        return args, {**kwargs, "progress_queue": queue}
    if "queue" in sig.parameters:
        return args, {**kwargs, "queue": queue}
    return args, kwargs


def _wants_progress_queue(func: Callable[..., Any]) -> bool:
    if not inspect.iscoroutinefunction(func):
        return False
    sig = inspect.signature(func)
    return "progress_queue" in sig.parameters or "queue" in sig.parameters


class TaskManager:
    """
    Submits work to the asynclet worker, tracks tasks, and trims completed entries.

    The manager acts as an in-memory registry keyed by task id (and optional
    `global:{name}` aliases). For rerun-driven UIs, keep a manager around when
    you create many tasks over time and periodically call `cleanup()`.
    """

    def __init__(self, *, max_completed: int = 256) -> None:
        self._tasks: Dict[str, Task[Any]] = {}
        self._lock = threading.Lock()
        self._max_completed = max_completed

    def submit(
        self,
        func: Callable[..., T],
        /,
        *args: Any,
        retry: Optional[RetryPolicy] = None,
        **kwargs: Any,
    ) -> Task[T]:
        """
        Submit `func` to the asynclet worker.

        Args:
            func: Sync or async callable to execute.
            *args: Positional arguments passed to `func` (after progress queue injection, if any).
            retry: Optional `RetryPolicy` for exception-based retries.
            **kwargs: Keyword arguments passed to `func`.

        Returns:
            A `Task[T]` handle that can be polled from the caller thread.
        """
        task_id = new_task_id()
        task: Task[T] = Task(task_id)
        with self._lock:
            self._tasks[task_id] = task
        submit_coro(self._execute(task, func, args, kwargs, retry=retry))
        self._cleanup_if_needed()
        return task

    def get(self, task_id: str) -> Optional[Task[Any]]:
        """Get a task by id, or `None` if missing."""
        with self._lock:
            return self._tasks.get(task_id)

    def cleanup(self) -> int:
        """
        Remove oldest completed tasks if the registry exceeds `max_completed`.

        Returns:
            Number of removed entries.
        """
        removed = 0
        with self._lock:
            done_ids = [tid for tid, t in self._tasks.items() if t.done]
            overflow = len(done_ids) - self._max_completed
            if overflow <= 0:
                return 0
            for tid in done_ids[:overflow]:
                self._tasks.pop(tid, None)
                removed += 1
        return removed

    def _cleanup_if_needed(self) -> None:
        with self._lock:
            completed = sum(1 for t in self._tasks.values() if t.done)
        if completed > self._max_completed:
            self.cleanup()

    async def _execute(
        self,
        task: Task[Any],
        func: Callable[..., Any],
        args: Tuple[Any, ...],
        kwargs: Dict[str, Any],
        *,
        retry: Optional[RetryPolicy],
    ) -> None:
        progress_q = None
        try:
            current = asyncio.current_task()
            if current is None:
                raise RuntimeError("asynclet: missing asyncio task")
            loop = asyncio.get_running_loop()
            task._bind_worker_task(current, loop)
            if task.status == TaskStatus.CANCELLED:
                raise asyncio.CancelledError

            started_at = retry.start_time() if retry is not None else 0.0
            attempt = 0

            if inspect.iscoroutinefunction(func) and _wants_progress_queue(func):
                import janus

                progress_q = janus.Queue()
                task._set_progress_queue(progress_q)
                args, kwargs = _bind_progress_queue(func, progress_q, args, kwargs)

            while True:
                if task.status == TaskStatus.CANCELLED:
                    raise asyncio.CancelledError
                try:
                    if inspect.iscoroutinefunction(func):
                        result = await func(*args, **kwargs)
                    else:
                        runner = asyncify(func)
                        result = await runner(*args, **kwargs)
                    if task.status != TaskStatus.CANCELLED:
                        task._complete_ok(result)
                    return
                except asyncio.CancelledError:
                    raise
                except Exception as exc:
                    if retry is None:
                        raise
                    if not retry.should_retry(exc):
                        raise
                    attempt += 1
                    if attempt >= retry.max_attempts:
                        raise
                    if retry.exceeded_elapsed(started_at):
                        raise
                    delay = retry.delay_for_attempt(attempt_index=attempt - 1)
                    if delay:
                        await asyncio.sleep(delay)
        except asyncio.CancelledError:
            task._complete_cancelled()
        except Exception as exc:
            if task.status != TaskStatus.CANCELLED:
                task._complete_error(exc)
        finally:
            if progress_q is not None:
                tail: List[Any] = []
                while True:
                    try:
                        tail.append(progress_q.sync_q.get_nowait())
                    except queue.Empty:
                        break
                task._buffer_progress_tail(tail)
                progress_q.close()
                await progress_q.wait_closed()
            task._clear_progress_queue_ref()

    def register_global(self, task: Task[Any], name: str) -> None:
        """
        Alias a task for shared lookup.

        After registering, `get(f"global:{name}")` returns the task.
        """
        with self._lock:
            self._tasks[f"global:{name}"] = task


def get_default_manager() -> TaskManager:
    """Return the process-wide default `TaskManager` (lazy singleton)."""
    global _default_manager
    with _default_manager_lock:
        if _default_manager is None:
            _default_manager = TaskManager()
        return _default_manager


def run(
    func: Callable[..., T],
    /,
    *args: Any,
    manager: Optional[TaskManager] = None,
    retry: Optional[RetryPolicy] = None,
    **kwargs: Any,
) -> Task[T]:
    """
    Run `func` on the asynclet worker thread and return a pollable `Task`.

    Async callables run on the dedicated worker event loop. Sync callables run via
    `asyncer.asyncify` (thread pool). If the async callable declares a `progress_queue`
    or `queue` parameter, a `janus.Queue` is created and injected to stream progress
    values back to the caller thread (drain via `Task.progress`).

    Args:
        func: Sync or async callable.
        *args: Positional args for `func` (after progress queue injection, if any).
        manager: Optional `TaskManager` to submit into (defaults to the process-wide manager).
        retry: Optional `RetryPolicy` for exception-based retries.
        **kwargs: Keyword args for `func`.

    Returns:
        A `Task[T]` handle.
    """
    m = manager or get_default_manager()
    return m.submit(func, *args, retry=retry, **kwargs)
