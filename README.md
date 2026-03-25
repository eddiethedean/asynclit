# asynclet

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

## Public API

| Item | Role |
|------|------|
| `asynclet.run(func, /, *args, manager=None, **kwargs)` | Submit `func` on the worker; returns a `Task`. |
| `Task.done` | Whether the result (or error) is ready. |
| `Task.result` | Result value; raises if not complete. |
| `Task.status` | `TaskStatus`: `PENDING`, `RUNNING`, `DONE`, `ERROR`, `CANCELLED`. |
| `Task.error` | Exception object when `status` is `ERROR`, else `None`. |
| `Task.cancel()` | Request cancellation (running tasks use asyncio cancellation; pending tasks cancel the result future). |
| `Task.progress` | Non-blocking drain of progress values (see below). |
| `TaskManager` / `get_default_manager()` | Custom registry and `cleanup()` when you keep many completed tasks. |
| `session_tasks(session_state)` | Dict stored on `st.session_state` for named tasks. |

## Progress (Janus)

For **async** functions only, declare a parameter named **`queue`** or **`progress_queue`**. If it is the **first** parameter, remaining positional arguments to `run()` map to the rest of the signature.

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

## How it works (short)

- One **daemon thread** runs a single **asyncio** event loop.
- **Async** callables run on that loop; **sync** callables run via [asyncer](https://github.com/tiangolo/asyncer)’s `asyncify` (thread pool).
- Submissions use `asyncio.run_coroutine_threadsafe`; results are bridged with a `concurrent.futures.Future` for the polling API.

## Development

```bash
pip install -e '.[dev]'
pytest
```

## License

MIT.
