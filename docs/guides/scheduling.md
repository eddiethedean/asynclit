# Scheduling (APScheduler)

Install the optional extra:

```bash
pip install 'asynclet[scheduler]'
```

## Interval scheduling

Each tick submits an asynclet task. If you set `latest_task_name`, asynclet stores the most recent `Task` under a manager global alias (`global:{name}`) so you can poll it from a UI.

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

print(f"scheduled_latest_done= {bool(latest and latest.done)}")
print(f"scheduled_latest_result= {latest.result if latest and latest.done else None}")

asynclet.shutdown_scheduler(wait=False)
```

Example output (after waiting for the first scheduled tick to finish):

```text
scheduled_latest_done= True
scheduled_latest_result= 1
```

## Cron scheduling

Cron uses APScheduler’s `CronTrigger.from_crontab` format.

```python
import asynclet

asynclet.schedule_cron(load_data, cron="*/5 * * * *", latest_task_name="load_data")
```

