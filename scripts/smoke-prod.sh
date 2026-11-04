#!/usr/bin/env bash
# Minimal production smoke test. Run after a deploy and before the P0 gate.
#
#   scripts/smoke-prod.sh https://retract-demo.duckdns.org
#
# It checks the three things a broken deploy gets wrong first: the API cannot reach
# its database/Redis, the frontend bundle is not served, or the agent is open to
# anonymous callers. It is intentionally dependency-free (curl only).
set -euo pipefail

HOST="${1:?usage: smoke-prod.sh https://retract-demo.duckdns.org}"
HOST="${HOST%/}"

echo "health:"
health=$(curl -fsS "$HOST/api/health")
printf '%s\n' "$health"
# The route returns {"status":"ok","db":"ok","redis":"ok"}; a 200 with a degraded
# dependency is not a passing deploy.
case "$health" in
  *'"status":"ok"'*'"db":"ok"'*'"redis":"ok"'*) ;;
  *)
    echo "health is not all-ok: $health" >&2
    exit 1
    ;;
esac

echo "frontend:"
code=$(curl -fsS -o /dev/null -w '%{http_code}' "$HOST/")
test "$code" = "200"

echo "agent auth (expect 401):"
code=$(curl -s -o /dev/null -w '%{http_code}' "$HOST/eve/v1/info")
if [ "$code" != "401" ]; then
  echo "expected 401 from /eve/v1/info, got $code" >&2
  exit 1
fi

echo "TLS:"
curl -fsS -o /dev/null "$HOST/"
echo "ok"
