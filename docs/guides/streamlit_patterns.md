# Streamlit patterns

## Named task per session

```python
import streamlit as st
import asynclet

tasks = asynclet.session_tasks(st.session_state)
if "load" not in tasks:
    tasks["load"] = asynclet.run(load_data)

task = tasks["load"]
if task.done:
    st.write(task.result)
else:
    st.write("Loading…")
```

Observed output in `tests/streamlit_apps/asynclet_poll_app.py` (AppTest runs):

```text
run 0 ['wait']
run 1 ['ready:138']
... last ['ready:138']
```

## Progress streaming (async only)

```python
import streamlit as st
import asynclet

async def job(queue, n: int) -> int:
    for i in range(n):
        await queue.async_q.put(i)
    return n

tasks = asynclet.session_tasks(st.session_state)
tasks.setdefault("job", asynclet.run(job, 5))

task = tasks["job"]
for x in task.progress:
    st.write(f"tick: {x}")
if task.done:
    st.write(f"done: {task.result}")
```

Observed output in `tests/streamlit_apps/asynclet_progress_app.py` (AppTest runs):

```text
run 0 ['started']
run 1 ['tick:0', 'tick:1', 'tick:2', 'tick:3', 'done:4']
... last ['done:4']
```

