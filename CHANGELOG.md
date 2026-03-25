# Changelog

## 0.2.1

- Fix edge cases around progress queue shutdown handling.
- Surface scheduler start/shutdown failures to callers and reset the default scheduler on shutdown.
- Polish docstrings and ensure docs examples are runnable with real outputs.

## 0.2.0

- Add `RetryPolicy` for exception-based retries with backoff.
- Add APScheduler-backed scheduling helpers (`schedule_interval`, `schedule_cron`) behind `asynclet[scheduler]`.
- Improve docs (guides + ReadTheDocs/Sphinx setup) and expand test coverage.

## 0.1.0

- Initial release: background worker loop, `Task` polling API, progress streaming (Janus), cancellation, and Streamlit session helpers.

