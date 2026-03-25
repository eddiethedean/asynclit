# asynclet

[![Read the Docs](https://readthedocs.org/projects/asynclet/badge/?version=latest)](https://asynclet.readthedocs.io/)
[![PyPI version](https://img.shields.io/pypi/v/asynclet.svg)](https://pypi.org/project/asynclet/)
[![Python versions](https://img.shields.io/pypi/pyversions/asynclet.svg)](https://pypi.org/project/asynclet/)
[![License](https://img.shields.io/pypi/l/asynclet.svg)](LICENSE)

**Documentation**: [asynclet.readthedocs.io](https://asynclet.readthedocs.io/)

Small **async task layer** for [Streamlit](https://streamlit.io/) (and similar “sync main thread + rerun” UIs): run sync or async work on a **dedicated background event loop**, then **poll** status, results, **progress**, and **cancellation** without blocking the UI thread.

## Install

```bash
pip install asynclet
```

Optional extras:

- **Streamlit** (for a typical app environment): `pip install 'asynclet[streamlit]'`
- **APScheduler** (optional timers/jobs): `pip install 'asynclet[scheduler]'`

Requires **Python 3.9+**.

## Quick start

```python
import streamlit as st
import asynclet

task = asynclet.run(fetch_data)

if task.done:
    st.write(task.result)
else:
    st.write("Loading…")
```

On each rerun, check `task.done` and read `task.result` when finished.

Example output (from the included test app `tests/streamlit_apps/asynclet_poll_app.py` via Streamlit AppTest):

```text
run 0 ['wait']
run 1 ['ready:138']
... last ['ready:138']
```

## Public API

| Item | Role |
|------|------|
| `asynclet.run(func, /, *args, manager=None, retry=None, **kwargs)` | Submit `func` on the worker; returns a `Task`. |
| `Task.done` | Whether the result (or error) is ready. |
| `Task.result` | Result value; raises if not complete. |
| `Task.status` | `TaskStatus`: `PENDING`, `RUNNING`, `DONE`, `ERROR`, `CANCELLED`. |
| `Task.error` | Exception object when `status` is `ERROR`, else `None`. |
| `Task.cancel()` | Request cancellation (running tasks use asyncio cancellation; pending tasks cancel the result future). |
| `Task.progress` | Non-blocking drain of progress values (see below). |
| `TaskManager` / `get_default_manager()` | Custom registry and `cleanup()` when you keep many completed tasks. |
| `session_tasks(session_state)` | Dict stored on `st.session_state` for named tasks. |
| `RetryPolicy` | Retry configuration for exception-based retries. |
| `schedule_interval(...)` / `schedule_cron(...)` | Schedule periodic task submissions (requires `asynclet[scheduler]`). |

## Progress (Janus)

Progress is supported for **async** functions only.

Declare a parameter named **`queue`** or **`progress_queue`**:

- If it is the **first** parameter, asynclet injects the Janus queue **positionally** and the remaining positional arguments to `run()` map to the rest of the signature.
- Otherwise, asynclet injects the queue by **keyword** (`queue=` / `progress_queue=`).

```python
async def job(queue, steps: int):
    for i in range(steps):
        await queue.async_q.put(i)
    return steps

task = asynclet.run(job, 10)
# Each rerun:
for x in task.progress:
    st.write(x)
```

The UI thread reads via `task.progress`, which pulls from the sync side of a [janus](https://github.com/aio-libs/janus) queue.

## Streamlit session state

```python
import streamlit as st
import asynclet

tasks = asynclet.session_tasks(st.session_state)
if "load" not in tasks:
    tasks["load"] = asynclet.run(load_data)

task = tasks["load"]
```

## Patterns

### Named tasks (per session)

Use `session_tasks(st.session_state)` as a stable dict to store tasks across reruns:

```python
tasks = asynclet.session_tasks(st.session_state)

if "load" not in tasks:
    tasks["load"] = asynclet.run(load_data)

task = tasks["load"]
```

### Cleanup (when you create many tasks)

If you create many tasks over time, keep them in a `TaskManager` and periodically call `cleanup()` to trim completed entries:

```python
m = asynclet.TaskManager(max_completed=256)
task = asynclet.run(load_data, manager=m)

# ... later:
m.cleanup()
```

## Errors

If the callable raises, `task.status` becomes `ERROR`, `task.error` holds the exception, and reading `task.result` re-raises it.

```python
if task.status == asynclet.TaskStatus.ERROR:
    st.error(f"failed: {task.error!r}")
elif task.done:
    st.write(task.result)
else:
    st.write("Loading…")
```

## Cancellation

`task.cancel()` requests cancellation:

- If the task is **running**, it schedules `asyncio` cancellation on the worker loop.
- If the task is still **pending** (not yet bound on the worker loop), it cancels the result future.

Treat `CANCELLED` as a terminal state in UI code.

### Cooperative cancellation patterns

- **Async jobs**: rely on `asyncio` cancellation; add cancellation checkpoints when doing long CPU work (break work into chunks; `await` occasionally).
- **Sync jobs**: cancellation is best-effort; the underlying threadpool work may continue running. Prefer chunked work that you can stop between chunks.

## Retries

Use `RetryPolicy` for exception-based retries (opt-in per `run()` / `TaskManager.submit()`).

```python
policy = asynclet.RetryPolicy(
    max_attempts=3,
    base_delay=0.1,
    max_delay=1.0,
    multiplier=2.0,
    jitter=0.0,
)

task = asynclet.run(fetch_data, retry=policy)
```

Retries stop when attempts are exhausted, the task is cancelled, or a raised exception does not match the policy.

## Scheduling (APScheduler)

Install with:

```bash
pip install 'asynclet[scheduler]'
```

Then schedule periodic task submission on the worker loop:

```python
asynclet.schedule_interval(load_data, seconds=60, latest_task_name="load_data")

# Later (poll the most recent task):
m = asynclet.get_default_manager()
latest = m.get("global:load_data")
if latest and latest.done:
    st.write(latest.result)
```

## Troubleshooting / FAQ

### Why does it keep showing `wait`?

In rerun-driven UIs, a single script run may finish before the background task completes. The usual pattern is: show `wait`, then on the next rerun read `task.done` / `task.result`.

In tests (or special cases), you may need to allow a small amount of wall time between reruns for the worker to finish.

## How it works (short)

- One **daemon thread** runs a single **asyncio** event loop.
- **Async** callables run on that loop; **sync** callables run via [asyncer](https://github.com/tiangolo/asyncer)’s `asyncify` (thread pool).
- Submissions use `asyncio.run_coroutine_threadsafe`; results are bridged with a `concurrent.futures.Future` for the polling API.

## Development

```bash
pip install -e '.[dev]'
pytest
```

### Development (uv)

If you use [uv](https://github.com/astral-sh/uv), you can run tests in a fresh env like:

```bash
uv venv
uv pip install -e '.[dev]'
uv run pytest
```

The **dev** extra includes Streamlit so CI can run headless **[AppTest](https://docs.streamlit.io/develop/api-reference/app-testing)** checks in `tests/test_streamlit_apptest.py` against the sample apps under `tests/streamlit_apps/`.

## Docs

Build the documentation (Sphinx + MyST):

```bash
uv venv
uv pip install -e '.[docs]'
uv run python -m sphinx -b html docs docs/_build/html
```

## License

MIT.
