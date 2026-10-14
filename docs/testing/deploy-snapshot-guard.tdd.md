# Deploy snapshot guard — audit and TDD evidence

Source: repository/deployment audit requested by the user; no plan file was
supplied.

## Audit findings

1. GitHub Actions only runs tests; it has no production deploy step.
2. Production systemd units all execute from `/root/diamond-site`; port 3000
   and 3001 each had one active listener during the audit.
3. The former archive extraction copied current files but did not know which
   files a prior release had removed. A renamed or deleted source file could
   therefore remain on the server as stale code.

## Guard added

`scripts/deploy_release_snapshot.sh` is the sole source-sync command in
`deploy.md`. It requires a clean working tree and current `origin/main`, locks
concurrent releases, archives the exact commit, preserves relative paths, and
writes `.diamond-deploy/commit` plus a managed manifest. On a later release it
removes only stale files listed by the prior managed manifest. Production
state directories are rejected and never removed.

## RED / GREEN record

- RED: `test_release_script_deploys_only_a_clean_origin_main_snapshot` failed
  because the guarded script did not exist.
- GREEN: all deploy snapshot and existing Telegram handoff contract tests
  passed after implementation.
- Static checks: `bash -n scripts/deploy_release_snapshot.sh` and
  `git diff --check` passed.

## Guarantees

| Guarantee | Test | Result |
| --- | --- | --- |
| Only clean, current `origin/main` is eligible for release | `tests/test_deploy_snapshot_contract.py` | PASS |
| A commit stamp and managed manifest record the exact deployment | `tests/test_deploy_snapshot_contract.py` | PASS |
| Old source is removed only if it was managed by the prior release | `tests/test_deploy_snapshot_contract.py` | PASS |
| `.env`, DB/data, media, uploads, cache, dependencies and secrets are protected | `tests/test_deploy_snapshot_contract.py` | PASS |
