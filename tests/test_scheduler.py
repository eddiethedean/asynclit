from __future__ import annotations

import time

import pytest

import asynclet

from .helpers import wait_done


apscheduler = pytest.importorskip("apscheduler")


def test_schedule_interval_submits_tasks_and_registers_latest_alias():
    m = asynclet.TaskManager()

    def work() -> int:
        return 123

    scheduled = asynclet.schedule_interval(
        work,
        seconds=0.05,
        manager=m,
        latest_task_name="work_latest",
        job_id="work_job",
        replace_existing=True,
    )
    assert scheduled.job_id == "work_job"
    assert scheduled.latest_task_key == "global:work_latest"

    # Wait for at least one tick to happen.
    deadline = time.monotonic() + 2.0
    latest = None
    while time.monotonic() < deadline:
        latest = m.get("global:work_latest")
        if latest is not None:
            break
        time.sleep(0.01)
    assert latest is not None

    wait_done(latest, timeout=5.0)
    assert latest.result == 123

    asynclet.shutdown_scheduler(wait=False)


def test_schedule_interval_updates_latest_alias_over_time():
    m = asynclet.TaskManager()
    counter: dict[str, int] = {"n": 0}

    def work() -> int:
        counter["n"] += 1
        return counter["n"]

    asynclet.schedule_interval(
        work,
        seconds=0.03,
        manager=m,
        latest_task_name="latest_count",
        job_id="count_job",
    )

    # Observe at least 2 different completed tasks via the alias.
    values: list[int] = []
    deadline = time.monotonic() + 3.0
    while time.monotonic() < deadline and len(set(values)) < 2:
        t = m.get("global:latest_count")
        if t is not None and t.done and t.status == asynclet.TaskStatus.DONE:
            values.append(t.result)
        time.sleep(0.02)
    assert len(set(values)) >= 2

    asynclet.shutdown_scheduler(wait=False)


def test_schedule_cron_runs_and_submits_task():
    m = asynclet.TaskManager()

    def work() -> int:
        return 5

    # CronTrigger.from_crontab uses minute-level resolution, so we don't
    # wait for an actual tick here (would be flaky/slow). We just verify job
    # creation succeeds and the returned metadata is correct.
    scheduled = asynclet.schedule_cron(
        work,
        cron="*/1 * * * *",
        manager=m,
        latest_task_name="cron_latest",
        job_id="cron_job",
        replace_existing=True,
    )
    assert scheduled.job_id == "cron_job"
    assert scheduled.latest_task_key == "global:cron_latest"

    asynclet.shutdown_scheduler(wait=False)
