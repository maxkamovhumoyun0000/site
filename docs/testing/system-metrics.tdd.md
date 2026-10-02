# Server monitoring TDD evidence

## RED

`tests/test_system_metrics.py` was added before the implementation. On the
production-compatible virtual environment it failed during test collection:

```text
ModuleNotFoundError: No module named 'backend.system_metrics'
```

## GREEN

After adding the dependency-free metric collector and threshold helpers:

```text
3 passed in 0.03s
```

The tests cover threshold recommendations, the normal-resource state, and the
important regression that the newest pressure event must be reported instead
of the numerically largest historical spike.

## Operational checks

- `python3 -m py_compile` covers the changed Python modules.
- `npx tsc --noEmit` validates the dashboard/navigation types.
- The production deploy runbook backs up PostgreSQL before syncing, then
  retains the two newest verified backups only.
