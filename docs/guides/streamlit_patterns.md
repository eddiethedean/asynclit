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

