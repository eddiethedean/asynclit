# Retries

Retries are **opt-in** and **exception-based**.

```python
import asynclet


calls = {"n": 0}


def flaky_fetch() -> str:
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

task = asynclet.run(flaky_fetch, retry=policy)

import time

while not task.done:
    time.sleep(0.01)

print(f"retries_calls= {calls['n']}")
print(f"retries_status= {task.status.value}")
if task.done:
    print(f"retries_result= {task.result}")
```

Example output (using a `fetch_data()` that fails twice then succeeds):

```text
retries_calls= 3
retries_status= done
retries_result= ok
```

Notes:

- Only raised exceptions are retried.
- Cancelling the task stops the current attempt and prevents further retries.

