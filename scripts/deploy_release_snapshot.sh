#!/usr/bin/env bash
# Deploy exactly one pushed Git snapshot while keeping production state intact.
#
# This is intentionally the only source-sync entry point for diamond-site.
# It prevents an IDE's uncommitted files from being released and records a
# manifest so files removed from a later commit cannot remain as stale code.
set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
REMOTE_HOST="${DIAMOND_DEPLOY_HOST:-root@31.220.87.193}"
REMOTE_ROOT="${DIAMOND_DEPLOY_ROOT:-/root/diamond-site}"
SSH_KEY="${DIAMOND_DEPLOY_SSH_KEY:-/home/xumoyun-maxkamov/.ssh/myserver.key}"
# accept-new pins the host key on first contact and then refuses a changed
# key (MITM); "no" silently accepted any key for every code push.
SSH_ARGS=(-i "$SSH_KEY" -o StrictHostKeyChecking=accept-new)

cd "$PROJECT_ROOT"

if [[ -n "$(git status --porcelain)" ]]; then
  echo "Refusing deployment: working tree is not clean. Commit or stash unrelated IDE changes first." >&2
  exit 1
fi

git fetch origin
DEPLOY_COMMIT="${1:-origin/main}"
DEPLOY_COMMIT="$(git rev-parse --verify "${DEPLOY_COMMIT}^{commit}")"
ORIGIN_MAIN_COMMIT="$(git rev-parse --verify origin/main^{commit})"
if [[ "$DEPLOY_COMMIT" != "$ORIGIN_MAIN_COMMIT" ]]; then
  echo "Refusing deployment: only the current origin/main commit may be released." >&2
  exit 1
fi

manifest_file="$(mktemp "${TMPDIR:-/tmp}/diamond-site-manifest.XXXXXX")"
remote_lock=""
lock_acquired=0
cleanup() {
  rm -f "$manifest_file"
  if [[ "$lock_acquired" == "1" && -n "$remote_lock" ]]; then
    ssh "${SSH_ARGS[@]}" "$REMOTE_HOST" "rmdir '$remote_lock' 2>/dev/null || true" >/dev/null 2>&1 || true
  fi
}
trap cleanup EXIT
git ls-tree -r --name-only "$DEPLOY_COMMIT" | LC_ALL=C sort > "$manifest_file"

# Fail before transfer if the repository ever starts tracking production state.
python3 - "$manifest_file" <<'PY'
from pathlib import PurePosixPath
import sys

protected_top_levels = {
    ".env", "data", "logs", "media", "uploads", "node_modules", ".next",
    ".venv", "venv", "secrets",
}
legacy_root_prefixes = ("fix", "patch", "modify", "migrate_", "test_", "update_")
for raw in open(sys.argv[1], encoding="utf-8"):
    path = PurePosixPath(raw.strip())
    if not path.parts or path.is_absolute() or ".." in path.parts:
        raise SystemExit(f"Unsafe repository path in deployment manifest: {raw!r}")
    if path.parts[0] in protected_top_levels:
        raise SystemExit(f"Protected production path is tracked by Git: {path}")
    # One-off repair scripts historically rewrote source files directly and
    # were easy to execute by mistake.  Production releases must never carry
    # a root-level fixer/migrator/test script; maintained tools belong below
    # scripts/ with an explicit name and reviewable call site.
    if len(path.parts) == 1 and path.name.startswith(legacy_root_prefixes):
        raise SystemExit(f"Legacy root script is not deployable: {path}")
PY

release_id="${DEPLOY_COMMIT:0:12}.$$"
remote_manifest="/tmp/diamond-site-manifest-${release_id}.txt"
remote_lock="/tmp/diamond-site-release.lock"

ssh "${SSH_ARGS[@]}" "$REMOTE_HOST" "mkdir -m 700 '$remote_lock'" || {
  echo "Refusing deployment: another Diamond Site release is in progress." >&2
  exit 1
}
lock_acquired=1
# git archive contains only tracked files from the exact commit. Relative paths
# are retained by tar, so app/page.tsx can never be flattened into project root.
git archive --format=tar "$DEPLOY_COMMIT" | \
  ssh "${SSH_ARGS[@]}" "$REMOTE_HOST" "cd '$REMOTE_ROOT' && tar -xf -"
scp "${SSH_ARGS[@]}" "$manifest_file" "$REMOTE_HOST:$remote_manifest"

# Remove only paths written by a previous successful snapshot deploy. This
# never uses a broad delete and never touches data, media, uploads or secrets.
ssh "${SSH_ARGS[@]}" "$REMOTE_HOST" \
  "python3 - '$REMOTE_ROOT' '$remote_manifest' '$DEPLOY_COMMIT'" <<'PY'
from pathlib import Path, PurePosixPath
import os
import sys

root = Path(sys.argv[1]).resolve()
new_manifest = Path(sys.argv[2])
commit = sys.argv[3]
state_dir = root / ".diamond-deploy"  # .diamond-deploy/managed-paths + commit
previous_manifest = state_dir / "managed-paths"
protected_top_levels = {
    ".env", "data", "logs", "media", "uploads", "node_modules", ".next",
    ".venv", "venv", "secrets",
}

def safe_relative(raw: str) -> Path:
    value = raw.strip()
    path = PurePosixPath(value)
    if not value or path.is_absolute() or ".." in path.parts or not path.parts:
        raise RuntimeError(f"unsafe managed path: {raw!r}")
    if path.parts[0] in protected_top_levels:
        raise RuntimeError(f"protected managed path: {value}")
    target = (root / Path(*path.parts)).resolve()
    if root not in target.parents:
        raise RuntimeError(f"managed path escapes project root: {value}")
    return target

new_paths = {line.strip() for line in new_manifest.read_text(encoding="utf-8").splitlines() if line.strip()}
for item in new_paths:
    safe_relative(item)

old_paths: set[str] = set()
if previous_manifest.is_file():
    old_paths = {line.strip() for line in previous_manifest.read_text(encoding="utf-8").splitlines() if line.strip()}

for item in sorted(old_paths - new_paths, reverse=True):
    target = safe_relative(item)
    if target.is_file() or target.is_symlink():
        target.unlink()
        parent = target.parent
        while parent != root:
            try:
                parent.rmdir()
            except OSError:
                break
            parent = parent.parent

state_dir.mkdir(mode=0o700, exist_ok=True)
temp_manifest = state_dir / ".managed-paths.tmp"
temp_manifest.write_text("\n".join(sorted(new_paths)) + "\n", encoding="utf-8")
os.replace(temp_manifest, previous_manifest)
(state_dir / "commit").write_text(commit + "\n", encoding="utf-8")
new_manifest.unlink(missing_ok=True)
print(f"release:commit={commit} files={len(new_paths)} stale_removed={len(old_paths - new_paths)}")
PY

remote_commit="$(ssh "${SSH_ARGS[@]}" "$REMOTE_HOST" "cat '$REMOTE_ROOT/.diamond-deploy/commit'")"
if [[ "$remote_commit" != "$DEPLOY_COMMIT" ]]; then
  echo "Release verification failed: server commit stamp does not match." >&2
  exit 1
fi
echo "release:verified=$DEPLOY_COMMIT"
