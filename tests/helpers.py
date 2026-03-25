"""Test helpers (not part of the package)."""

from __future__ import annotations

import asyncio
import time
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from asynclit.task import Task


def wait_done(task: Task[Any], *, timeout: float = 15.0, poll: float = 0.005) -> None:
    deadline = time.monotonic() + timeout
    while not task.done and time.monotonic() < deadline:
        time.sleep(poll)
    assert task.done, (
        f"task {task.id!r} did not finish within {timeout}s (status={task.status!r})"
    )


async def wait_done_async(
    task: Task[Any], *, timeout: float = 15.0, poll: float = 0.005
) -> None:
    deadline = time.monotonic() + timeout
    while not task.done and time.monotonic() < deadline:
        await asyncio.sleep(poll)
    assert task.done, (
        f"task {task.id!r} did not finish within {timeout}s (status={task.status!r})"
    )
