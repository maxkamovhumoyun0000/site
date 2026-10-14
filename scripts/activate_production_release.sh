#!/usr/bin/env bash
# Activate one already-synced Diamond Site release on the production server.
#
# Run this *on the server* only after deploy_release_snapshot.sh has recorded
# the same commit in .diamond-deploy/commit.  It serializes frontend builds,
# restores the previous Next build if a new build fails, and only starts the
# public frontend after backend and bot services have been restarted.
set -euo pipefail

PROJECT_ROOT="${DIAMOND_RELEASE_ROOT:-/root/diamond-site}"
EXPECTED_COMMIT="${1:-}"
LOCK_PATH="/tmp/diamond-site-release.lock"
FRONTEND_SERVICE="diamond-site-frontend"
BACKEND_SERVICES=(
  diamond-site-backend
  diamond-site-admin-bot
  diamond-site-student-bot
  diamond-site-support-bot
  diamond-site-teacher-bot
)

if [[ ! "$EXPECTED_COMMIT" =~ ^[0-9a-f]{40}$ ]]; then
  echo "Usage: $0 <40-character deployed Git commit>" >&2
  exit 2
fi

cd "$PROJECT_ROOT"
if [[ ! -f .diamond-deploy/commit ]] || [[ "$(tr -d '\n' < .diamond-deploy/commit)" != "$EXPECTED_COMMIT" ]]; then
  echo "Refusing activation: .diamond-deploy/commit does not match the requested release." >&2
  exit 1
fi

if ! mkdir -m 700 "$LOCK_PATH"; then
  echo "Refusing activation: another Diamond Site release is in progress." >&2
  exit 1
fi
cleanup() {
  rmdir "$LOCK_PATH" 2>/dev/null || true
}
trap cleanup EXIT

wait_for_inactive() {
  local service="$1"
  for _ in $(seq 1 30); do
    if ! systemctl is-active --quiet "$service"; then
      return 0
    fi
    sleep 1
  done
  echo "Timed out waiting for $service to stop." >&2
  return 1
}

wait_for_http() {
  local url="$1"
  for _ in $(seq 1 30); do
    if curl --fail --silent --show-error --max-time 5 "$url" >/dev/null; then
      return 0
    fi
    sleep 1
  done
  echo "Timed out waiting for $url." >&2
  return 1
}

# Validate dependencies and Python source before disrupting the running site.
npm ci
.venv/bin/python -m py_compile \
  admin_bot.py student_bot.py teacher_bot.py support_lesson.py attendance_manager.py \
  payment.py db.py backend/main.py bot_runtime.py

previous_next=".next.previous.$(date +%s).$$"
had_previous_next=0
restore_previous_frontend() {
  if [[ "$had_previous_next" == "1" && -d "$previous_next" ]]; then
    rm -rf -- .next
    mv -- "$previous_next" .next
    systemctl start "$FRONTEND_SERVICE" || true
  fi
}

systemctl stop "$FRONTEND_SERVICE"
wait_for_inactive "$FRONTEND_SERVICE"
if ss -ltn '( sport = :3000 )' | grep -q ':3000'; then
  echo "Refusing build: TCP port 3000 is still occupied after frontend stop." >&2
  exit 1
fi

if [[ -d .next ]]; then
  mv -- .next "$previous_next"
  had_previous_next=1
fi

if ! npm run build; then
  echo "Frontend build failed; restoring the previous verified .next build." >&2
  restore_previous_frontend
  exit 1
fi

systemctl restart "${BACKEND_SERVICES[@]}"
wait_for_http "http://127.0.0.1:3001/health/ready"

systemctl start "$FRONTEND_SERVICE"
wait_for_http "http://127.0.0.1:3000/"

rm -rf -- "$previous_next"
echo "release:active=$EXPECTED_COMMIT"
