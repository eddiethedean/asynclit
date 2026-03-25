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
    """Handle for work running on the asynclet worker loop."""

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
        return self._status

    @property
    def done(self) -> bool:
        return self._result_fut.done()

    @property
    def result(self) -> T:
        if not self._result_fut.done():
            raise RuntimeError("Task is not complete")
        return self._result_fut.result()

    @property
    def error(self) -> Optional[BaseException]:
        return self._error

    @property
    def progress(self) -> List[Any]:
        """Drain pending progress values (non-blocking) from the Janus queue and any buffered tail."""
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
        """Request cancellation. Returns True if cancellation was scheduled or the result future was cancelled."""
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
