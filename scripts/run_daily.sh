#!/bin/zsh
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
export TZ="${DIGEST_TIMEZONE:-Europe/Moscow}"
cd "$ROOT_DIR"
export PYTHONPATH="src"

if [[ -f ".env" ]]; then
  set -a
  source ".env"
  set +a
fi

STATE_DIR="${STATE_DIR:-$ROOT_DIR/state}"
mkdir -p "$STATE_DIR"

LOCK_DIR="$STATE_DIR/run_daily.lock"
RUN_LOG="$STATE_DIR/cron_daily.log"
HEARTBEAT_LOG="$STATE_DIR/cron_daily_heartbeat.log"

timestamp() {
  date -u +"%Y-%m-%dT%H:%M:%SZ"
}

heartbeat() {
  printf '[%s] status=%s pid=%s host=%s\n' "$(timestamp)" "$1" "$$" "$(hostname -s 2>/dev/null || hostname)" >> "$HEARTBEAT_LOG"
}

if ! mkdir "$LOCK_DIR" 2>/dev/null; then
  heartbeat "skipped_lock"
  exit 0
fi

cleanup() {
  rmdir "$LOCK_DIR" 2>/dev/null || true
}

trap cleanup EXIT
heartbeat "started"

run_digest() {
  if command -v caffeinate >/dev/null 2>&1; then
    caffeinate -dimsu zsh -c 'python3 -m digest_bot.main daily'
  else
    python3 -m digest_bot.main daily
  fi
}

set +e
{
  printf '\n[%s] run_daily.sh started\n' "$(timestamp)"
  run_digest
} >> "$RUN_LOG" 2>&1
status=$?
set -e

if [[ $status -eq 0 ]]; then
  heartbeat "completed"
else
  heartbeat "failed"
fi

exit "$status"
