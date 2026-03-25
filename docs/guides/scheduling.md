# Scheduling (APScheduler)

Install the optional extra:

```bash
pip install 'asynclet[scheduler]'
```

## Interval scheduling

Each tick submits an asynclet task. If you set `latest_task_name`, asynclet stores the most recent `Task` under a manager global alias (`global:{name}`) so you can poll it from a UI.

```python
import asynclet

asynclet.schedule_interval(load_data, seconds=60, latest_task_name="load_data")

m = asynclet.get_default_manager()
latest = m.get("global:load_data")
if latest and latest.done:
    print(latest.result)
```

## Cron scheduling

Cron uses APScheduler’s `CronTrigger.from_crontab` format.

```python
import asynclet

asynclet.schedule_cron(load_data, cron="*/5 * * * *", latest_task_name="load_data")
```

