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
CADDY_CONFIG="/etc/caddy/Caddyfile"
CADDY_MAINTENANCE_ROUTE="/etc/caddy/diamond-site-maintenance.caddy"
CADDY_MAINTENANCE_PAGE="/var/www/diamond-site-maintenance.html"
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
maintenance_enabled=0
previous_next=""
had_previous_next=0
set_platform_maintenance() {
  local enabled="$1"
  .venv/bin/python - "$enabled" <<'PY'
import sys
from db import update_app_version_settings
enabled = 1 if sys.argv[1] == "1" else 0
update_app_version_settings({
    "platform_maintenance_enabled": enabled,
    "platform_maintenance_message_uz": "Texnik ishlar olib borilmoqda. Taxminan 30 daqiqa ichida qaytamiz.",
    "platform_maintenance_message_ru": "Проводятся технические работы. Ориентировочно вернёмся через 30 минут.",
    "platform_maintenance_message_en": "Technical work is in progress. We expect to be back in about 30 minutes.",
})
PY
}
set_site_maintenance() {
  local enabled="$1"
  if [[ "$enabled" == "1" ]]; then
    install -D -m 0644 scripts/maintenance.html "$CADDY_MAINTENANCE_PAGE"
    install -m 0644 scripts/caddy-maintenance-active.caddy "$CADDY_MAINTENANCE_ROUTE"
  else
    install -m 0644 scripts/caddy-maintenance-inactive.caddy "$CADDY_MAINTENANCE_ROUTE"
  fi
  caddy validate --config "$CADDY_CONFIG" --adapter caddyfile
  caddy reload --config "$CADDY_CONFIG" --adapter caddyfile
}
ensure_caddy_maintenance_route() {
  if [[ ! -f "$CADDY_CONFIG" ]]; then
    echo "Caddy config not found: $CADDY_CONFIG" >&2
    return 1
  fi
  if ! grep -q 'diamond-site-maintenance.caddy' "$CADDY_CONFIG"; then
    local backup="${CADDY_CONFIG}.diamond-maintenance.bak"
    if [[ ! -f "$backup" ]]; then
      cp -a -- "$CADDY_CONFIG" "$backup"
    fi
    .venv/bin/python - "$CADDY_CONFIG" <<'PY'
import sys
from pathlib import Path

path = Path(sys.argv[1])
source = path.read_text(encoding="utf-8")
lines = source.splitlines(keepends=True)
anchor = "diamond-education.uz {\n"
if lines.count(anchor) != 1:
    raise SystemExit("Expected exactly one diamond-education.uz Caddy site block")
index = lines.index(anchor)
lines.insert(index + 1, "\timport /etc/caddy/diamond-site-maintenance.caddy\n")
source = "".join(lines)
temporary = path.with_name(path.name + ".diamond-tmp")
temporary.write_text(source, encoding="utf-8")
temporary.chmod(path.stat().st_mode)
temporary.replace(path)
PY
    install -D -m 0644 scripts/caddy-maintenance-inactive.caddy "$CADDY_MAINTENANCE_ROUTE"
  fi
  if ! caddy validate --config "$CADDY_CONFIG" --adapter caddyfile; then
    local backup="${CADDY_CONFIG}.diamond-maintenance.bak"
    if [[ -f "$backup" ]]; then
      cp -a -- "$backup" "$CADDY_CONFIG"
      caddy validate --config "$CADDY_CONFIG" --adapter caddyfile || true
    fi
    return 1
  fi
  caddy reload --config "$CADDY_CONFIG" --adapter caddyfile
}
restore_previous_frontend() {
  if [[ "$had_previous_next" == "1" && -n "$previous_next" && -d "$previous_next" ]]; then
    rm -rf -- .next
    mv -- "$previous_next" .next
    had_previous_next=0
    systemctl start "$FRONTEND_SERVICE" || true
  fi
}
cleanup() {
  local exit_code=$?
  if [[ "$maintenance_enabled" == "1" ]]; then
    restore_previous_frontend
    if systemctl is-active --quiet "$FRONTEND_SERVICE" && wait_for_http http://127.0.0.1:3000/; then
      set_site_maintenance 0 || true
      set_platform_maintenance 0 || true
    else
      echo "Release activation failed; maintenance remains enabled because the frontend is not healthy." >&2
    fi
  fi
  rmdir "$LOCK_PATH" 2>/dev/null || true
  return "$exit_code"
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

# Install the reverse-proxy fallback before stopping Next.js so website
# visitors get a real localized page throughout the frontend build/restart.
ensure_caddy_maintenance_route
maintenance_enabled=1
set_site_maintenance 1
set_platform_maintenance 1
systemctl restart "${BACKEND_SERVICES[@]}"
wait_for_http "http://127.0.0.1:3001/health/ready"

previous_next=".next.previous.$(date +%s).$$"

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

set_platform_maintenance 0
set_site_maintenance 0
maintenance_enabled=0

rm -rf -- "$previous_next"
echo "release:active=$EXPECTED_COMMIT"
