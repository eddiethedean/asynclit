# asynclit — package specification

## 1. Overview

**asynclit** is an async task layer aimed at [Streamlit](https://streamlit.io/) (and similar environments with a synchronous UI thread and rerun-driven updates). It provides:

- Background execution of **sync** and **async** callables  
- **Non-blocking** UI updates via **polling** (`task.done`, `task.result`, …)  
- **Progress** streaming through a Janus queue  
- **Task lifecycle** management: status, result, error, cancel  
- Optional hooks for **session-scoped** task registries and **scheduler** integration  

The library does not replace Streamlit’s execution model; it complements it by moving work off the main thread while keeping the UI pattern simple.

---

## 2. Goals

- Preserve Streamlit’s **rerun** model (no mandatory long-lived blocking calls on the script thread).  
- Provide a **small, obvious API** for offloading work.  
- Support **sync and async** functions without forcing callers to manage an event loop.  
- Avoid requiring users to understand **asyncio** beyond optional progress/cancel semantics.  

---

## 3. Core architecture

### 3.1 Async worker

- A **dedicated daemon thread** hosts a single **asyncio** event loop for the process (lazy-started on first use).  
- Work is submitted with `asyncio.run_coroutine_threadsafe` from other threads.  

### 3.2 Task manager

- **`TaskManager`** registers tasks by id, exposes **`submit()`**, **`get()`**, and **`cleanup()`** (trim oldest completed entries when a configurable cap is exceeded).  
- **`asynclit.run(..., manager=None)`** uses a process-wide **default manager** from **`get_default_manager()`** when `manager` is omitted.  
- **`register_global(task, name)`** stores an alias keyed as `global:{name}` for shared lookup via **`get()`**.  

### 3.3 Janus queue (progress)

- When an **async** callable opts in (see §8), a **`janus.Queue`** is created on the worker loop.  
- The worker pushes progress on **`queue.async_q`**; the UI thread reads by draining **`task.progress`** (sync side + any tail buffered when the queue is closed).  

### 3.4 Scheduler (optional)

- **APScheduler** is an **optional dependency** (`asynclit[scheduler]`).  
- asynclit provides scheduling helpers that create an `AsyncIOScheduler` bound to the worker loop and schedule jobs that submit asynclit tasks.

---

## 4. Dependencies

| Component        | Role |
|-----------------|------|
| **asyncer**     | `asyncify` for running sync callables from the worker loop (thread pool). |
| **janus**       | Sync/async queue for progress streaming. |
| **asyncio**     | Worker event loop (stdlib). |
| **concurrent.futures** | Result bridge for cross-thread polling (`Future`). |
| **APScheduler** | Optional; not required at runtime for core features. |
| **Streamlit**   | Optional; only needed for apps using `st.*`; **`session_tasks`** accepts any mapping (e.g. `st.session_state`). |

---

## 5. Public API

### 5.1 Run task

```python
task = asynclit.run(func, /, *args, manager=None, **kwargs)
```

- **`manager`**: optional **`TaskManager`**; must not collide with keyword arguments intended for **`func`** (reserved keyword for `run` only).  

### 5.2 Task surface

```python
task.id
task.done
task.result       # raises if not complete
task.status       # TaskStatus enum
task.error        # set when status is ERROR
task.cancel()     # returns bool
task.progress     # list: non-blocking drain of pending progress values
```

### 5.3 Session and managers

```python
asynclit.session_tasks(session_state, key="asynclit_tasks")
asynclit.get_default_manager()
asynclit.TaskManager(max_completed=256)
```

---

## 6. Task lifecycle

**`TaskStatus`**: `PENDING` → `RUNNING` → `DONE` | `ERROR` | `CANCELLED`

| State        | Meaning |
|-------------|---------|
| **PENDING** | Submitted; worker coroutine may not have bound the asyncio task yet. |
| **RUNNING** | Worker asyncio task is bound; callable is executing. |
| **DONE**    | Finished successfully; result available (subject to `task.done`). |
| **ERROR**   | Exception captured; exposed via **`task.error`** and **`task.result`** (raises). |
| **CANCELLED** | User cancellation or cancelled future before completion. |

---

## 7. Internal design (conceptual)

### 7.1 Task object

- **`id: str`** — unique task identifier.  
- **Result bridge** — `concurrent.futures.Future` for cross-thread completion.  
- **Progress** — optional Janus queue handle while running; internal tail buffer for values drained at close so late polls still observe progress.  
- **Status** — **`TaskStatus`**.  
- **Worker reference** — bound **`asyncio.Task`** and loop for cancellation.  

### 7.2 Task manager

- **`submit(func, /, *args, **kwargs)`** → **`Task`**  
- **`get(task_id)`** → **`Task | None`**  
- **`cleanup()`** → count removed (completed-task cap)  

---

## 8. Progress streaming

Progress is supported only for **async** callables that declare a parameter named **`queue`** or **`progress_queue`**.

- If that parameter is the **first** parameter, the injected queue is passed **positionally** and remaining **`run(...)`** positional arguments map to the rest of the signature.  
- Otherwise the queue is passed as the corresponding **keyword** argument.  

Worker side:

```python
async def job(queue, steps: int) -> int:
    for i in range(steps):
        await queue.async_q.put(i)
    return steps
```

UI side: read **`task.progress`** on each rerun (or poll in a loop); values are drained from the sync side of the Janus queue.

---

## 9. Session handling

- Callers store **`Task`** references in **`st.session_state`** (or any mutable mapping).  
- **`session_tasks(session_state, key=...)`** returns a **dict** stored at **`session_state[key]`** for named tasks.  
- **`TaskManager.register_global`** / **`get("global:{name}")`** support optional **shared aliases** inside a manager.  

### 9.1 Rerun-driven UIs and polling

In Streamlit-style rerun models, the script run that *submits* the task will usually finish before the background work completes. The intended usage is to:

- Store the `Task` (for example in session state)
- On subsequent reruns, check `task.done` / `task.status`
- Read `task.result` only once it is complete

---

## 10. Error handling

- Exceptions from the user callable are stored on the task and **`Future.set_exception`**.  
- **`task.error`** holds the exception when **`task.status == TaskStatus.ERROR`**.  
- Accessing **`task.result`** when complete but failed re-raises the stored exception.  

---

## 10.1 Retries

Retries are **opt-in** and **exception-based**.

- A **`RetryPolicy`** can be provided per submission (for example via `asynclit.run(..., retry=...)`).
- Only raised exceptions are eligible for retry; returned values are not inspected.
- Cancellation stops any ongoing attempt and prevents further retries.

---

## 11. Cancellation

- **Pending** (not yet bound to a worker asyncio task): **`concurrent.futures.Future.cancel()`** and status **`CANCELLED`**.  
- **Running**: **`asyncio.Task.cancel()`** scheduled on the worker loop; completion ends in **`CANCELLED`** with the result future cancelled if still pending.  

---

## 12. Performance considerations

- **Single global worker event loop** per process (simple, predictable).  
- **Thread-safe** manager and task state where required.  
- **Bounded registry**: **`cleanup()`** / automatic trim via **`max_completed`** to limit memory from finished tasks.  

---

## 13. Example usage

```python
import streamlit as st
import asynclit

task = asynclit.run(fetch_data)

if task.done:
    st.write(task.result)
else:
    st.write("Loading…")
```

