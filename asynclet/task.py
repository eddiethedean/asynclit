from __future__ import annotations

import asyncio
import queue
import threading
import uuid
from concurrent import futures
from enum import Enum
from typing import Any, Generic, List, Optional, TypeVar

T = TypeVar("T")


class TaskStatus(Enum):
    PENDING = "pending"
    RUNNING = "running"
    DONE = "done"
    ERROR = "error"
    CANCELLED = "cancelled"


class Task(Generic[T]):
    """
    A poll-friendly handle for work running on the asynclet worker loop.

    `Task` is designed for synchronous, rerun-driven UIs (e.g. Streamlit):
    submit work, keep the handle somewhere stable (session state), and on each
    rerun poll `done` / `status` and read `result` when ready.

    Notes:
    - Results are bridged via a `concurrent.futures.Future`, so polling does not
      require an event loop on the caller thread.
    - Progress is available only when the submitted callable is **async** and
      declares a `queue` or `progress_queue` parameter (see `asynclet.run`).
    """

    def __init__(self, task_id: str) -> None:
        self.id = task_id
        self._status = TaskStatus.PENDING
        self._result_fut: futures.Future[T] = futures.Future()
        self._error: Optional[BaseException] = None
        self._progress_queue: Any = None
        self._progress_tail: List[Any] = []
        self._asyncio_task: Optional[asyncio.Task[Any]] = None
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._lock = threading.Lock()

    @property
    def status(self) -> TaskStatus:
        """Current lifecycle status."""
        return self._status

    @property
    def done(self) -> bool:
        """Whether the task has completed (success, error, or cancellation)."""
        return self._result_fut.done()

    @property
    def result(self) -> T:
        """
        Return the result value.

        Raises:
            RuntimeError: If the task is not complete yet.
            BaseException: Re-raises the underlying exception if the task failed.
            concurrent.futures.CancelledError: If the task was cancelled.
        """
        if not self._result_fut.done():
            raise RuntimeError("Task is not complete")
        return self._result_fut.result()

    @property
    def error(self) -> Optional[BaseException]:
        """The captured exception if `status` is `ERROR`, otherwise `None`."""
        return self._error

    @property
    def progress(self) -> List[Any]:
        """
        Drain progress values (non-blocking).

        This returns any values currently available on the sync side of the Janus
        queue, plus any tail buffered when the queue was closed (so late polls can
        still observe final progress).

        Returns:
            A list of values in FIFO order. Empty when no progress is available.
        """
        out: List[Any] = []
        q = self._progress_queue
        if q is not None:
            sync_q = q.sync_q
            while True:
                try:
                    out.append(sync_q.get_nowait())
                except queue.Empty:
                    break
                except Exception as exc:
                    # janus raises when the queue is closed and drained
                    if exc.__class__.__name__ in ("ShutDown", "SyncQueueShutDown"):
                        break
                    raise
        if self._progress_tail:
            out.extend(self._progress_tail)
            self._progress_tail.clear()
        return out

    def cancel(self) -> bool:
        """
        Request cancellation.

        Behavior:
        - If the task is already terminal (`DONE`, `ERROR`, `CANCELLED`), returns `False`.
        - If the underlying asyncio task is running, schedules `asyncio.Task.cancel()`
          on the worker loop and returns `True`.
        - If the task is still pending (not yet bound on the worker), cancels the
          result future and returns whether it was cancelled.

        Returns:
            `True` if a cancellation request was scheduled/performed, otherwise `False`.
        """
        with self._lock:
            if self._status in (
                TaskStatus.DONE,
                TaskStatus.ERROR,
                TaskStatus.CANCELLED,
            ):
                return False
            aio_task = self._asyncio_task
            loop = self._loop
            pending = self._status == TaskStatus.PENDING
        if aio_task is not None and loop is not None and not aio_task.done():

            def _cancel() -> None:
                aio_task.cancel()

            loop.call_soon_threadsafe(_cancel)
            return True
        if pending:
            with self._lock:
                self._status = TaskStatus.CANCELLED
            return self._result_fut.cancel()
        return False

    def _bind_worker_task(
        self, aio_task: asyncio.Task[Any], loop: asyncio.AbstractEventLoop
    ) -> None:
        with self._lock:
            self._asyncio_task = aio_task
            self._loop = loop
            if self._status != TaskStatus.CANCELLED:
                self._status = TaskStatus.RUNNING

    def _set_progress_queue(self, queue_obj: Any) -> None:
        self._progress_queue = queue_obj

    def _clear_progress_queue_ref(self) -> None:
        self._progress_queue = None

    def _buffer_progress_tail(self, items: List[Any]) -> None:
        if items:
            self._progress_tail.extend(items)

    def _complete_ok(self, value: T) -> None:
        with self._lock:
            if self._status == TaskStatus.CANCELLED:
                return
            self._status = TaskStatus.DONE
        if not self._result_fut.done():
            self._result_fut.set_result(value)

    def _complete_error(self, exc: BaseException) -> None:
        with self._lock:
            if self._status == TaskStatus.CANCELLED:
                return
            self._status = TaskStatus.ERROR
            self._error = exc
        if not self._result_fut.done():
            self._result_fut.set_exception(exc)

    def _complete_cancelled(self) -> None:
        with self._lock:
            self._status = TaskStatus.CANCELLED
        if not self._result_fut.done():
            self._result_fut.cancel()


def new_task_id() -> str:
    return str(uuid.uuid4())
