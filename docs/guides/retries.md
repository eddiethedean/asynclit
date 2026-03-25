# Retries

Retries are **opt-in** and **exception-based**.

```python
import asynclet

policy = asynclet.RetryPolicy(
    max_attempts=5,
    retry_on=(RuntimeError,),
    base_delay=0.1,
    multiplier=2.0,
    max_delay=2.0,
    jitter=0.0,
)

task = asynclet.run(fetch_data, retry=policy)
```

Notes:

- Only raised exceptions are retried.
- Cancelling the task stops the current attempt and prevents further retries.

