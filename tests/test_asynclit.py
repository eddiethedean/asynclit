from __future__ import annotations

import asyncio
import concurrent.futures
import re
import threading
import time
import uuid

import pytest

import asynclit

from .helpers import wait_done, wait_done_async


def test_run_sync_function():
    def add(a: int, b: int) -> int:
        return a + b

    task = asynclit.run(add, 2, 3)
    wait_done(task)
    assert task.status == asynclit.TaskStatus.DONE
    assert task.error is None
    assert task.result == 5


@pytest.mark.asyncio
async def test_run_async_coroutine():
    async def double(x: int) -> int:
        await asyncio.sleep(0.01)
        return x * 2

    task = asynclit.run(double, 21)
    await wait_done_async(task)
    assert task.result == 42


@pytest.mark.asyncio
async def test_progress_queue_first_param():
    async def emit(progress_queue, n: int) -> int:
        for i in range(n):
            await progress_queue.async_q.put(i)
        return n

    task = asynclit.run(emit, 4)
    seen: list[int] = []
    await wait_done_async(task)
    seen.extend(task.progress)
    assert task.result == 4
    assert seen == [0, 1, 2, 3]


@pytest.mark.asyncio
async def test_progress_queue_keyword_injected_second_param():
    async def keyed(n: int, progress_queue) -> int:
        await progress_queue.async_q.put("tick")
        return n

    task = asynclit.run(keyed, 9)
    await wait_done_async(task)
    assert task.progress == ["tick"]
    assert task.result == 9


@pytest.mark.asyncio
async def test_progress_tail_readable_after_done_without_mid_poll():
    async def burst(queue, n: int) -> int:
        for i in range(n):
            await queue.async_q.put(i)
        return n

    task = asynclit.run(burst, 3)
    await wait_done_async(task)
    assert task.progress == [0, 1, 2]
    assert task.progress == []


@pytest.mark.asyncio
async def test_progress_tail_drain_tolerates_shutdown_exception(
    monkeypatch: pytest.MonkeyPatch,
):
    # Ensure the manager's final tail-drain doesn't fail if the sync queue proxy
    # raises a shutdown exception (janus raises these when closed + drained).
    import sys

    class ShutDown(Exception):
        pass

    class FakeSyncQ:
        def get_nowait(self):
            raise ShutDown()

    class FakeJanusQueue:
        def __init__(self):
            self.sync_q = FakeSyncQ()
            self.async_q = object()

        def close(self) -> None:
            return None

        async def wait_closed(self) -> None:
            return None

    class FakeJanus:
        @staticmethod
        def Queue():
            return FakeJanusQueue()

    monkeypatch.setitem(sys.modules, "janus", FakeJanus)

    async def uses_progress(queue) -> int:
        return 1

    task = asynclit.run(uses_progress)
    await wait_done_async(task)
    assert task.result == 1


def test_result_raises_runtime_error_when_not_complete():
    def slow() -> int:
        time.sleep(0.3)
        return 1

    task = asynclit.run(slow)
    assert not task.done
    with pytest.raises(RuntimeError, match="not complete"):
        _ = task.result


def test_async_error_surfaces():
    async def bad() -> None:
        await asyncio.sleep(0.01)
        raise RuntimeError("async boom")

    task = asynclit.run(bad)
    wait_done(task)
    assert task.status == asynclit.TaskStatus.ERROR
    assert task.error is not None
    assert str(task.error) == "async boom"
    with pytest.raises(RuntimeError, match="async boom"):
        _ = task.result


def test_error_surfaces_on_sync_task():
    def boom() -> None:
        raise ValueError("nope")

    task = asynclit.run(boom)
    wait_done(task)
    assert task.status == asynclit.TaskStatus.ERROR
    with pytest.raises(ValueError, match="nope"):
        _ = task.result


def test_cancel_idempotent_when_error():
    def boom() -> None:
        raise RuntimeError("bad")

    task = asynclit.run(boom)
    wait_done(task)
    assert task.status == asynclit.TaskStatus.ERROR
    assert task.cancel() is False
    assert task.status == asynclit.TaskStatus.ERROR
    assert task.error is not None
    with pytest.raises(RuntimeError, match="bad"):
        _ = task.result


def test_cancel_running_task():
    async def slow() -> str:
        await asyncio.sleep(60)
        return "done"

    task = asynclit.run(slow)
    time.sleep(0.05)
    assert task.cancel() is True
    wait_done(task)
    assert task.status == asynclit.TaskStatus.CANCELLED


def test_cancel_pending_before_worker_binds_eventually_cancelled():
    async def never_scheduled_long() -> None:
        await asyncio.sleep(3600)

    seen_cancelled = 0
    for _ in range(30):
        task = asynclit.run(never_scheduled_long)
        if task.cancel():
            wait_done(task, timeout=5.0)
            if task.status == asynclit.TaskStatus.CANCELLED:
                seen_cancelled += 1
                with pytest.raises(concurrent.futures.CancelledError):
                    _ = task.result
    assert seen_cancelled >= 1


def test_cancel_idempotent_when_done():
    def ok() -> int:
        return 42

    task = asynclit.run(ok)
    wait_done(task)
    assert task.cancel() is False
    assert task.status == asynclit.TaskStatus.DONE
    assert task.result == 42


def test_cancel_idempotent_when_already_cancelled():
    async def slow() -> None:
        await asyncio.sleep(30)

    task = asynclit.run(slow)
    time.sleep(0.05)
    assert task.cancel() is True
    wait_done(task)
    assert task.status == asynclit.TaskStatus.CANCELLED
    assert task.cancel() is False


def test_custom_task_manager_isolated_from_default():
    m = asynclit.TaskManager()

    def ident(x: int) -> int:
        return x

    task = asynclit.run(ident, 7, manager=m)
    wait_done(task)
    assert m.get(task.id) is not None
    assert asynclit.get_default_manager().get(task.id) is None


def test_manager_get_missing_returns_none():
    m = asynclit.TaskManager()
    assert m.get(str(uuid.uuid4())) is None


def test_manager_register_global_alias():
    m = asynclit.TaskManager()

    def f() -> str:
        return "ok"

    task = m.submit(f)
    m.register_global(task, "shared")
    wait_done(task)
    got = m.get("global:shared")
    assert got is task
    assert got.result == "ok"


def test_manager_cleanup_removes_oldest_completed():
    m = asynclit.TaskManager(max_completed=2)

    def ident(x: int) -> int:
        return x

    t0 = m.submit(ident, 0)
    t1 = m.submit(ident, 1)
    t2 = m.submit(ident, 2)
    wait_done(t0)
    wait_done(t1)
    wait_done(t2)
    removed = m.cleanup()
    assert removed == 1
    assert m.get(t0.id) is None
    assert m.get(t1.id) is not None
    assert m.get(t2.id) is not None


def test_session_tasks_creates_stable_bucket():
    state: dict = {}
    a = asynclit.session_tasks(state, key="bucket")
    b = asynclit.session_tasks(state, key="bucket")
    assert a is b
    assert "bucket" in state


def test_task_id_is_uuid_v4():
    def noop() -> None:
        return None

    task = asynclit.run(noop)
    wait_done(task)
    assert re.fullmatch(
        r"[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}",
        task.id,
    )


def test_concurrent_tasks_all_succeed():
    def work(i: int) -> int:
        time.sleep(0.02)
        return i * 3

    tasks = [asynclit.run(work, i) for i in range(6)]
    for t in tasks:
        wait_done(t)
    assert [t.result for t in tasks] == [i * 3 for i in range(6)]


def test_concurrent_tasks_finish_out_of_order():
    def work(i: int) -> int:
        # Invert sleep so later tasks can finish earlier.
        time.sleep(0.02 * (6 - i))
        return i

    tasks = [asynclit.run(work, i) for i in range(6)]
    time.sleep(0.05)
    assert any(t.done for t in tasks)
    assert any(not t.done for t in tasks)
    for t in tasks:
        wait_done(t)
        assert t.status == asynclit.TaskStatus.DONE
    assert sorted([t.result for t in tasks]) == list(range(6))


def test_sync_function_runs_off_worker_thread():
    main = threading.current_thread()

    def whoami() -> threading.Thread:
        return threading.current_thread()

    task = asynclit.run(whoami)
    wait_done(task)
    assert task.result is not main


@pytest.mark.asyncio
async def test_async_coroutine_runs_on_worker_loop():
    loop_ids: dict[str, int] = {}

    async def capture() -> int:
        loop_ids["id"] = id(asyncio.get_running_loop())
        return 1

    task = asynclit.run(capture)
    await wait_done_async(task)
    worker_loop_id = loop_ids["id"]

    captured: dict[str, int] = {}

    async def here() -> None:
        captured["id"] = id(asyncio.get_running_loop())

    await here()
    assert captured["id"] != worker_loop_id


def test_run_passes_kwargs_to_callable():
    def greet(*, name: str, punct: str = "!") -> str:
        return f"hi {name}{punct}"

    task = asynclit.run(greet, name="ada", punct="?")
    wait_done(task)
    assert task.result == "hi ada?"


@pytest.mark.asyncio
async def test_async_without_progress_queue():
    async def add(a: int, b: int) -> int:
        await asyncio.sleep(0.01)
        return a + b

    task = asynclit.run(add, 40, 2)
    await wait_done_async(task)
    assert task.progress == []
    assert task.result == 42


@pytest.mark.asyncio
async def test_progress_mid_run_drains_without_duplication():
    async def emit(queue) -> int:
        for i in range(3):
            await queue.async_q.put(i)
            await asyncio.sleep(0.02)
        return 3

    task = asynclit.run(emit)
    collected: list[int] = []
    while not task.done:
        collected.extend(task.progress)
        await asyncio.sleep(0.005)
    collected.extend(task.progress)
    assert task.result == 3
    assert collected == [0, 1, 2]
    assert task.progress == []


def test_retry_policy_delay_computation():
    p = asynclit.RetryPolicy(
        max_attempts=3, base_delay=0.1, multiplier=2.0, max_delay=1.0, jitter=0.0
    )
    assert p.delay_for_attempt(0) == pytest.approx(0.1)
    assert p.delay_for_attempt(1) == pytest.approx(0.2)
    assert p.delay_for_attempt(2) == pytest.approx(0.4)


def test_retries_sync_function_eventually_succeeds():
    calls = {"n": 0}

    def flaky() -> int:
        calls["n"] += 1
        if calls["n"] < 3:
            raise RuntimeError("nope")
        return 7

    task = asynclit.run(
        flaky, retry=asynclit.RetryPolicy(max_attempts=5, base_delay=0.0)
    )
    wait_done(task)
    assert task.status == asynclit.TaskStatus.DONE
    assert task.result == 7
    assert calls["n"] == 3


@pytest.mark.asyncio
async def test_retries_async_function_eventually_succeeds():
    calls = {"n": 0}

    async def flaky() -> int:
        calls["n"] += 1
        if calls["n"] < 3:
            raise RuntimeError("nope")
        return 9

    task = asynclit.run(
        flaky, retry=asynclit.RetryPolicy(max_attempts=5, base_delay=0.0)
    )
    await wait_done_async(task)
    assert task.status == asynclit.TaskStatus.DONE
    assert task.result == 9
    assert calls["n"] == 3


def test_retries_stop_after_max_attempts():
    calls = {"n": 0}

    def always() -> None:
        calls["n"] += 1
        raise ValueError("bad")

    task = asynclit.run(
        always,
        retry=asynclit.RetryPolicy(
            max_attempts=3, base_delay=0.0, retry_on=(ValueError,)
        ),
    )
    wait_done(task)
    assert task.status == asynclit.TaskStatus.ERROR
    assert calls["n"] == 3
    with pytest.raises(ValueError, match="bad"):
        _ = task.result


def test_retries_do_not_retry_on_unmatched_exception():
    calls = {"n": 0}

    def always() -> None:
        calls["n"] += 1
        raise KeyError("k")

    task = asynclit.run(
        always,
        retry=asynclit.RetryPolicy(
            max_attempts=5, base_delay=0.0, retry_on=(ValueError,)
        ),
    )
    wait_done(task)
    assert task.status == asynclit.TaskStatus.ERROR
    assert calls["n"] == 1
    with pytest.raises(KeyError):
        _ = task.result


def test_retry_policy_retry_if_predicate_blocks_retry():
    calls = {"n": 0}

    def always() -> None:
        calls["n"] += 1
        raise RuntimeError("stop")

    policy = asynclit.RetryPolicy(
        max_attempts=5,
        base_delay=0.0,
        retry_on=(RuntimeError,),
        retry_if=lambda exc: "nope" in str(exc),
    )
    task = asynclit.run(always, retry=policy)
    wait_done(task)
    assert task.status == asynclit.TaskStatus.ERROR
    assert calls["n"] == 1


def test_retry_policy_max_elapsed_stops_retrying():
    calls = {"n": 0}

    def always() -> None:
        calls["n"] += 1
        raise RuntimeError("nope")

    policy = asynclit.RetryPolicy(
        max_attempts=10,
        base_delay=0.02,
        retry_on=(RuntimeError,),
        max_elapsed=0.05,
        jitter=0.0,
    )
    task = asynclit.run(always, retry=policy)
    wait_done(task)
    assert task.status == asynclit.TaskStatus.ERROR
    # We don't assert exact attempts (timing), but it should stop before max_attempts.
    assert 1 <= calls["n"] < 10


def test_cancel_stops_retry_loop():
    calls = {"n": 0}

    def always() -> None:
        calls["n"] += 1
        raise RuntimeError("nope")

    policy = asynclit.RetryPolicy(
        max_attempts=100, base_delay=0.01, retry_on=(RuntimeError,), jitter=0.0
    )
    task = asynclit.run(always, retry=policy)
    time.sleep(0.05)
    assert task.cancel() is True
    wait_done(task)
    assert task.status == asynclit.TaskStatus.CANCELLED
    before = calls["n"]
    time.sleep(0.05)
    assert calls["n"] == before


def test_worker_loop_singleton():
    import asynclit.worker as worker

    loop_a = worker.get_worker_loop()
    loop_b = worker.get_worker_loop()
    assert loop_a is loop_b


def test_manager_submit_matches_run_with_same_manager():
    m = asynclit.TaskManager()

    def double(x: int) -> int:
        return x * 2

    t_submit = m.submit(double, 11)
    t_run = asynclit.run(double, 11, manager=m)
    wait_done(t_submit)
    wait_done(t_run)
    assert t_submit.result == 22
    assert t_run.result == 22
