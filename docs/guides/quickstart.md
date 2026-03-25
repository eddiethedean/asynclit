# Quickstart

```python
import asynclet

task = asynclet.run(lambda: 21 * 2)
if task.done:
    print(task.result)
else:
    print("working…")
```

In rerun-driven UIs (like Streamlit), you typically store the `Task` in session state and poll it across reruns.

