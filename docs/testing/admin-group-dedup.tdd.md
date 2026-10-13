# Admin group creation de-duplication — TDD evidence

## Regression

`/admin/groups` POST response was inserted twice in the Groups screen:

1. the shared `onAdminCall` mutation handler inserted it; and
2. the create-modal callback inserted the same response again.

The next GET refresh replaced the local list and hid the duplicate, which is
why the issue disappeared after a manual refresh.

## Contract

`tests/test_admin_group_dedup_contract.py` requires one centralized,
ID-based `upsertAdminGroupRow` path and rejects a second modal append.

## Verification

```bash
python3 - <<'PY'
import importlib.util
spec = importlib.util.spec_from_file_location('group_contract', 'tests/test_admin_group_dedup_contract.py')
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
module.test_admin_group_creation_uses_one_idempotent_upsert_path()
PY
git diff --check
```

The production Next.js build is the final TypeScript check because this local
workspace intentionally has no installed TypeScript/eslint dev dependencies.
