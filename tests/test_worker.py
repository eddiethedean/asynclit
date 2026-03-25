from __future__ import annotations

import asyncio

import pytest

import asynclet


@pytest.mark.asyncio
async def test_submit_coro_from_inside_worker_loop_returns_future():
    import asynclet.worker as worker

    seen: dict[str, int] = {}

    async def inner() -> int:
        async def small() -> int:
            await asyncio.sleep(0.01)
            return 42

        fut = worker.submit_coro(small())
        # submit_coro returns a concurrent.futures.Future even when called
        # from inside the worker loop (scheduler jobs rely on this behavior).
        seen["type"] = (
            1 if fut.__class__.__module__.startswith("concurrent.futures") else 0
        )
        # Do NOT call fut.result() here: this function runs on the worker loop and
        # blocking would deadlock the loop.
        deadline = asyncio.get_running_loop().time() + 2.0
        while not fut.done() and asyncio.get_running_loop().time() < deadline:
            await asyncio.sleep(0.01)
        assert fut.done()
        return fut.result()

    task = asynclet.run(inner)
    # Wait from this test loop.
    deadline = asyncio.get_running_loop().time() + 5.0
    while not task.done and asyncio.get_running_loop().time() < deadline:
        await asyncio.sleep(0.01)
    assert task.done
    assert task.result == 42
    assert seen["type"] == 1
