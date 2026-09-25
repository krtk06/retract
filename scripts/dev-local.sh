#!/usr/bin/env bash
# Local development stack (no Docker): Postgres must already be running.
#
# Usage: scripts/dev-local.sh [start|stop|restart]
# Machine-specific settings live in .local/env.sh (gitignored), e.g.:
#   AI_INTEL_DATABASE_URL=postgresql+psycopg://user@/ai_intel?host=/var/run/postgresql&port=5433
#   AI_INTEL_REDIS_URL=redis://localhost:6390/0
#   AI_INTEL_DEV_LOGIN=1
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

API_PORT="${API_PORT:-8110}"
REDIS_PORT="${REDIS_PORT:-6390}"
LOG_DIR="${LOG_DIR:-/tmp}"
REDIS_BIN="${REDIS_BIN:-$ROOT/.local/bin/redis-server}"
VENV="$ROOT/backend/.venv"

if [[ -f "$ROOT/.local/env.sh" ]]; then
  # shellcheck disable=SC1091
  source "$ROOT/.local/env.sh"
fi

start_redis() {
  if ! "$REDIS_BIN" --version >/dev/null 2>&1; then
    echo "redis-server not found at $REDIS_BIN (see README local development)"; exit 1
  fi
  if ! "$VENV/bin/python" -c "import redis; redis.Redis.from_url('${AI_INTEL_REDIS_URL}').ping()" 2>/dev/null; then
    "$REDIS_BIN" --port "$REDIS_PORT" --daemonize yes --save "" --appendonly no
    sleep 1
  fi
  echo "redis ok on $REDIS_PORT"
}

start_app() {
  pkill -9 -f "uvicorn app.main:app" 2>/dev/null || true
  pkill -9 -f "celery -A app.tasks.celery_app" 2>/dev/null || true
  sleep 1
  (cd backend && setsid nohup "$VENV/bin/uvicorn" app.main:app --host 127.0.0.1 --port "$API_PORT" \
    > "$LOG_DIR/api.log" 2>&1 < /dev/null &)
  (cd backend && setsid nohup "$VENV/bin/celery" -A app.tasks.celery_app:celery_app worker -l info -c 2 \
    > "$LOG_DIR/worker.log" 2>&1 < /dev/null &)
  sleep 4
  echo "api: http://127.0.0.1:$API_PORT/api/health"
}

stop_all() {
  pkill -9 -f "uvicorn app.main:app" 2>/dev/null || true
  pkill -9 -f "celery -A app.tasks.celery_app" 2>/dev/null || true
  echo "api + worker stopped (redis left running)"
}

case "${1:-start}" in
  start) start_redis; start_app ;;
  stop) stop_all ;;
  restart) stop_all; sleep 1; start_redis; start_app ;;
  *) echo "usage: $0 [start|stop|restart]"; exit 2 ;;
esac
