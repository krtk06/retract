#!/usr/bin/env bash
# Local development stack (no Docker): Postgres must already be running.
#
# Usage: scripts/dev-local.sh [start|stop|restart]
# Machine-specific settings live in .local/env.sh (gitignored), e.g.:
#   RETRACT_DATABASE_URL=postgresql+psycopg://user@/ai_intel?host=/var/run/postgresql&port=5433
#   RETRACT_REDIS_URL=redis://localhost:6390/0
#   RETRACT_DEV_LOGIN=1
#   RETRACT_AGENT_TOKEN=<shared secret the eve agent presents to the API>
#
# Starts: redis, api (:8110), celery worker, eve agent (:3000), vite (:5175).
# The eve agent needs Node >= 24 and shares RETRACT_JWT_SECRET with the API so
# the browser's exchanged eve token verifies on its routes.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

API_PORT="${API_PORT:-8110}"
EVE_PORT="${EVE_PORT:-3000}"
FRONTEND_PORT="${FRONTEND_PORT:-5175}"
REDIS_PORT="${REDIS_PORT:-6390}"
LOG_DIR="${LOG_DIR:-/tmp}"
REDIS_BIN="${REDIS_BIN:-$ROOT/.local/bin/redis-server}"
VENV="$ROOT/backend/.venv"

if [[ -f "$ROOT/.env" ]]; then
  # Sourced first so `.local/env.sh` keeps precedence for machine-specific values.
  # The backend reads `.env` itself (pydantic-settings), but the agent does not —
  # eve has no dotenv loading — so without this the LLM provider and credential set
  # for `.env` would never reach a source-run agent, and `openai` would silently run
  # as the mock (or fail on a missing key) locally while looking configured.
  set -a
  # shellcheck disable=SC1091
  source "$ROOT/.env"
  set +a
fi

if [[ -f "$ROOT/.local/env.sh" ]]; then
  # shellcheck disable=SC1091
  source "$ROOT/.local/env.sh"
fi

# eve requires Node 24; use the caller's PATH when it already satisfies that.
node_major() {
  node --version 2>/dev/null | sed 's/^v\([0-9]*\).*/\1/'
}

load_node24() {
  if [[ -s "$HOME/.nvm/nvm.sh" ]]; then
    export NVM_DIR="${NVM_DIR:-$HOME/.nvm}"
    # shellcheck disable=SC1091
    source "$NVM_DIR/nvm.sh"
  fi
  if command -v nvm >/dev/null 2>&1; then
    nvm use 24 >/dev/null
  fi
  if [[ "$(node_major)" -lt 24 ]]; then
    echo "Node >= 24 required for the eve agent (found $(node --version 2>/dev/null || echo none))"
    echo "Install it with: source ~/.nvm/nvm.sh && nvm install 24"
    exit 1
  fi
}

start_redis() {
  if ! "$REDIS_BIN" --version >/dev/null 2>&1; then
    echo "redis-server not found at $REDIS_BIN (see README local development)"; exit 1
  fi
  if ! "$VENV/bin/python" -c "import redis; redis.Redis.from_url('${RETRACT_REDIS_URL}').ping()" 2>/dev/null; then
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
  echo "retract-api: http://127.0.0.1:$API_PORT/api/health"
}

start_agent() {
  if [[ "${SKIP_AGENT:-0}" == "1" ]]; then
    echo "retract-agent: skipped (SKIP_AGENT=1)"
    return
  fi
  load_node24
  pkill -9 -f "eve dev" 2>/dev/null || true
  sleep 1
  (cd agent && PORT="$EVE_PORT" setsid nohup npx eve dev --no-ui \
    > "$LOG_DIR/eve.log" 2>&1 < /dev/null &)
  sleep 6
  echo "retract-agent: http://127.0.0.1:$EVE_PORT/eve (log: $LOG_DIR/eve.log)"
}

start_frontend() {
  if [[ "${SKIP_FRONTEND:-0}" == "1" ]]; then
    echo "retract-frontend: skipped (SKIP_FRONTEND=1)"
    return
  fi
  pkill -9 -f "vite --port" 2>/dev/null || true
  sleep 1
  (cd frontend && PORT="$FRONTEND_PORT" VITE_API_PROXY="http://127.0.0.1:$API_PORT" \
    VITE_EVE_PROXY="http://127.0.0.1:$EVE_PORT" \
    setsid nohup npm run dev -- --port "$FRONTEND_PORT" \
    > "$LOG_DIR/vite.log" 2>&1 < /dev/null &)
  sleep 4
  echo "retract-frontend: http://127.0.0.1:$FRONTEND_PORT"
}

stop_all() {
  pkill -9 -f "uvicorn app.main:app" 2>/dev/null || true
  pkill -9 -f "celery -A app.tasks.celery_app" 2>/dev/null || true
  pkill -9 -f "eve dev" 2>/dev/null || true
  pkill -9 -f "vite --port" 2>/dev/null || true
  echo "api, worker, agent, and frontend stopped (redis left running)"
}

case "${1:-start}" in
  start) start_redis; start_app; start_agent; start_frontend ;;
  stop) stop_all ;;
  restart) stop_all; sleep 1; start_redis; start_app; start_agent; start_frontend ;;
  *) echo "usage: $0 [start|stop|restart]"; exit 2 ;;
esac
