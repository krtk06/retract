#!/usr/bin/env bash
# Capture the demo screenshots from the local stack.
#
#   scripts/capture-demo.sh [base-url] [output-dir] [analysis-id]
#
# Defaults: http://localhost:5173, docs/demo, and the newest completed analysis.
# Pass an analysis id to keep a storyboard on one repository.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BASE="${1:-http://localhost:5173}"
BASE="${BASE%/}"
OUT="${2:-$ROOT/docs/demo}"
ANALYSIS_ID="${3:-}"

if ! command -v agent-browser >/dev/null 2>&1; then
  echo "agent-browser is not installed. See https://github.com/vercel-labs/agent-browser" >&2
  exit 1
fi
if ! curl -fsS "$BASE/" >/dev/null; then
  echo "Nothing is serving $BASE. Start the stack with:" >&2
  echo "  docker compose --env-file .env -f infra/docker-compose.yml up --build" >&2
  exit 1
fi

mkdir -p "$OUT"

agent-browser open "$BASE"
agent-browser wait --load networkidle
# The button only exists when the API has dev login enabled. An existing session
# skips the login page, so a miss is not an error.
agent-browser find text "Dev login" click >/dev/null 2>&1 || true
agent-browser wait --text "Recent analyses"
agent-browser screenshot "$OUT/01-dashboard.png"

agent-browser open "$BASE/repos"
agent-browser wait --text "Analyze a repository"
agent-browser screenshot "$OUT/02-repositories.png"

latest="$ANALYSIS_ID"
if [ -z "$latest" ]; then
  latest=$(
    agent-browser eval "fetch('/api/analyses').then(r => r.json()).then(rows => { const row = rows.find(item => item.status === 'done'); return row ? String(row.id) : ''; })" |
      tr -d '[:space:]"'
  )
fi
if [ -z "$latest" ]; then
  echo "No completed analysis. Add a repository in the UI, wait for the run, then rerun." >&2
  exit 0
fi

agent-browser open "$BASE/analyses/$latest"
agent-browser wait --load networkidle
# The score is fetched after the analysis payload; give it one tick so the
# screenshot does not capture the stale score embedded in the analysis row.
agent-browser wait 1000
agent-browser screenshot "$OUT/03-overview.png"

agent-browser scroll down 900
agent-browser wait 500
agent-browser screenshot "$OUT/04-findings.png"

# Expand the first finding's source excerpt.
agent-browser find text "show code" click
agent-browser wait 500
agent-browser screenshot "$OUT/05-finding.png"

# The tabs are React buttons with role=tab; clicking by text avoids a snapshot
# dependency on refs that change after the code excerpt opens.
agent-browser eval "Array.from(document.querySelectorAll('[role=tab]')).find(t => t.textContent.trim().toLowerCase() === 'fixes')?.click()"
agent-browser wait 800
agent-browser scroll up 1200
agent-browser wait 300
agent-browser screenshot "$OUT/06-fixes.png"

echo "Saved screenshots to $OUT"
echo "Capture the agent answer manually: open the Agent tab, ask a question, wait for the answer, then screenshot."
