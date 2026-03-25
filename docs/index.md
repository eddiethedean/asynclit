# asynclet

Async task layer for Streamlit-style “rerun” UIs.

Use asynclet when you need to kick off background work without blocking the UI thread, then **poll** for completion across reruns. It supports:

- **Sync + async** callables
- **Polling** (`task.done`, `task.status`, `task.result`, `task.error`)
- **Progress streaming** (async jobs via a Janus queue)
- **Cancellation**
- **Scheduling** (optional APScheduler-backed helpers)

## Install

```bash
pip install asynclet
```

Optional extras:

```bash
pip install 'asynclet[streamlit]'
pip install 'asynclet[scheduler]'
```

## Quick examples

### Submit work and poll

```python
import asynclet

task = asynclet.run(lambda: 21 * 2)
if task.done:
    print(task.result)
else:
    print("working…")
```

### Stream progress (async only)

```python
import asynclet

async def job(queue, steps: int) -> int:
    for i in range(steps):
        await queue.async_q.put(i)
    return steps

task = asynclet.run(job, 4)
for x in task.progress:
    print("tick", x)
```

### Retry transient failures

```python
import asynclet

calls = {"n": 0}


def fetch_data() -> str:
    calls["n"] += 1
    if calls["n"] < 3:
        raise RuntimeError("transient")
    return "ok"

policy = asynclet.RetryPolicy(
    max_attempts=5,
    retry_on=(RuntimeError,),
    base_delay=0.1,
    multiplier=2.0,
    max_delay=2.0,
    jitter=0.0,
)

task = asynclet.run(fetch_data, retry=policy)
print("retries_calls=", calls["n"])
print("retries_status=", task.status.value)
if task.done:
    print("retries_result=", task.result)
```

### Schedule periodic jobs (APScheduler)

```python
import asynclet

counter = {"n": 0}


def load_data() -> int:
    counter["n"] += 1
    return counter["n"]


asynclet.schedule_interval(load_data, seconds=0.05, latest_task_name="load_data")

m = asynclet.get_default_manager()
latest = None

import time

deadline = time.monotonic() + 2.0
while time.monotonic() < deadline:
    latest = m.get("global:load_data")
    if latest and latest.done:
        break
    time.sleep(0.01)

print("scheduled_latest_done=", bool(latest and latest.done))
print("scheduled_latest_result=", latest.result if latest and latest.done else None)

asynclet.shutdown_scheduler(wait=False)
```

## Where to go next

- Start with **Quickstart** for the basic mental model.
- Use **Streamlit patterns** for session-state storage and progress UI.
- See **Retries** and **Scheduling** for resilience and periodic work.

```{toctree}
---
maxdepth: 2
caption: Guides
---

guides/quickstart
guides/streamlit_patterns
guides/retries
guides/scheduling
```

```{toctree}
---
maxdepth: 2
caption: Reference
---

reference/api
reference/spec
```

