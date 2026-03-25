# asynclet roadmap

This document tracks intended direction for **asynclet**. It is aspirational: priorities and versions can change. For behavior and API details, see [`docs/asynclet-spec.md`](docs/asynclet-spec.md).

---

## Current release line (0.1.x)

**Theme:** solid baseline for Streamlit-style polling UIs.

Already in scope for this line:

- Dedicated **worker thread** with a single **asyncio** loop  
- **`asynclet.run`** for **sync** (via asyncer `asyncify`) and **async** callables  
- **`Task`**: `done`, `result`, `status`, `error`, `cancel`, `progress`  
- **Janus**-based **progress** for async jobs (`queue` / `progress_queue`)  
- **`TaskManager`**, default manager, **`cleanup`**, optional **`register_global`**  
- **`session_tasks`** helper for `st.session_state` (or any mapping)  
- Optional **`[scheduler]`** extra; loop access for advanced integration  

Possible **patch** work (still 0.1.x):

### Completed (0.1.x)

- Docs and examples (Streamlit snippets, edge cases)
  - Added a “patterns” section: session-scoped tasks, named tasks, and cleanup guidance
  - Documented progress queue injection rules (`queue`/`progress_queue`, positional vs keyword)
  - Documented cancellation semantics (pending vs running) and what callers should expect
  - Added a troubleshooting/FAQ for rerun timing gotchas (“why does it stay `wait`?”)
  - Expanded examples to show error handling (`task.status`, `task.error`) and user-land retry patterns
- Typing and API polish without breaking changes
  - Ensured `asynclet/scheduler.py` optional export is typed cleanly when APScheduler is missing
- Test coverage for races and cancellation edge cases
  - Added coverage for pending-cancellation result behavior
  - Added concurrency coverage for out-of-order completion and registry consistency
  - Added cancellation idempotency coverage (including cancel-after-error)
  - Added progress tests for mid-run polling (drain behavior) vs tail buffering after completion

---

## Next (0.2)

**Theme:** scheduling and resilience.

### Completed (0.2)

- **APScheduler**: first-class wrapper API (optional via `asynclet[scheduler]`)
  - `get_default_scheduler()`, `start_scheduler()`, `shutdown_scheduler()`
  - `schedule_interval(...)` and `schedule_cron(...)` (jobs submit asynclet tasks; optional “latest task” alias)
- **Retries**: exception-based `RetryPolicy` with backoff (opt-in per `run` / `TaskManager.submit`)
- **Cancellation**: clearer cooperative-cancel patterns documented (async vs sync caveats)

---

## Later (0.3+)

**Theme:** scale-out and richer integrations.

- **Distributed backends** (optional): e.g. **Celery** or **Ray** as pluggable executors, keeping the same `Task` polling model where feasible  
- **WebSocket** or other **push** channels alongside polling  
- **Plugins** for custom transports or observability (metrics, tracing)  

---

## 1.0 and beyond

**Theme:** stability and ecosystem.

- **Stable API** commitment and deprecation policy  
- **Reactive** patterns: tighter optional integration with Streamlit state/widgets where it does not fight the rerun model  
- Broader **examples** and **cookbook** patterns (long-running jobs, fan-out, progress UX)  

---

## How to contribute

Open issues or PRs on the project repository with concrete use cases. Roadmap items move faster when tied to real apps and clear API sketches.
