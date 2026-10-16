#!/usr/bin/env bash
# Read-only preflight for the dedicated Diamond Speaking LiveKit media node.
# It deliberately never starts/stops Docker, changes DNS, edits firewall rules,
# or restarts the Diamond API service.
set -euo pipefail

mode="${1:-}"
case "$mode" in
  backend|media) ;;
  *)
    echo "Usage: LIVEKIT_MEDIA_IP=<public-ip> $0 {backend|media}" >&2
    exit 64
    ;;
esac

failures=0
check() {
  local description="$1"
  shift
  if "$@"; then
    printf 'PASS  %s\n' "$description"
  else
    printf 'FAIL  %s\n' "$description" >&2
    failures=$((failures + 1))
  fi
}

if [[ "$mode" == "backend" ]]; then
  check 'LIVEKIT_URL is secure websocket URL' bash -c '[[ "${LIVEKIT_URL:-}" == "wss://live.diamond-education.uz" ]]'
  check 'LIVEKIT_INTERNAL_URL is secure media control URL' bash -c '[[ "${LIVEKIT_INTERNAL_URL:-}" == "https://live.diamond-education.uz" ]]'
  check 'LIVEKIT_API_KEY is set' bash -c '[[ -n "${LIVEKIT_API_KEY:-}" ]]'
  check 'LIVEKIT_API_SECRET is set and not short' bash -c 'secret="${LIVEKIT_API_SECRET:-}"; [[ ${#secret} -ge 32 ]]'
else
  media_ip="${LIVEKIT_MEDIA_IP:-}"
  check 'LIVEKIT_MEDIA_IP is provided' bash -c '[[ -n "${LIVEKIT_MEDIA_IP:-}" ]]'
  if [[ -n "$media_ip" ]]; then
    check 'live DNS resolves to the media VM' bash -c 'getent ahostsv4 live.diamond-education.uz | awk "{print \$1}" | grep -Fxq "$LIVEKIT_MEDIA_IP"'
    check 'TURN DNS resolves to the media VM' bash -c 'getent ahostsv4 turn.live.diamond-education.uz | awk "{print \$1}" | grep -Fxq "$LIVEKIT_MEDIA_IP"'
  fi
  check 'Docker Compose is available' bash -c 'docker compose version >/dev/null 2>&1'
  check 'official generated compose file exists' test -f /opt/livekit/docker-compose.yaml
  check 'official generated LiveKit config exists' test -f /opt/livekit/livekit.yaml
  check 'generated secret environment file is protected' bash -c 'test -f /opt/livekit/.env && test "$(stat -c %a /opt/livekit/.env)" -le 600'
fi

if (( failures > 0 )); then
  printf '\nLiveKit preflight failed: %s check(s) need attention. Nothing was changed.\n' "$failures" >&2
  exit 1
fi

printf '\nLiveKit %s preflight passed. Nothing was changed.\n' "$mode"
