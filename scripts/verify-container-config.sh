#!/usr/bin/env bash
# Static validation of the container build inputs.
#
# A Docker daemon is not always available (this repo is developed on a host whose
# socket is not accessible), but most first-run failures are static and can be
# caught without building:
#
#   * a COPY whose source does not exist in the build context
#   * a .dockerignore with no negation rule, so a future COPY under an ignored
#     path silently ships nothing
#   * a CMD naming an npm script the image's package.json does not define
#   * a compose build context that does not resolve
#   * a compose build target that is not a declared stage in its Dockerfile
#   * an agent provider/model build arg that compose forgot to pass
#   * a proxy-trust or budget variable that stops at the wrong container
#   * `docker compose config` rejecting the production file
#
# This does NOT prove the images build. The `containers` CI job does that.
set -uo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

failures=0
note() { printf '  %s\n' "$*"; }
fail() { printf '  FAIL %s\n' "$*"; failures=$((failures + 1)); }

# Every arg of a COPY except the last is a source; the last is the destination.
copy_sources() {
  local line="$1"
  read -ra parts <<<"$line"
  local last=$((${#parts[@]} - 1))
  local out=() from_stage=0
  for ((i = 1; i < last; i++)); do
    case "${parts[i]}" in
      --from=*) from_stage=1; continue ;;
    esac
    (( from_stage )) && continue
    out+=("${parts[i]}")
  done
  printf '%s\n' "${out[@]}"
}

check_dockerfile() {
  local dir="$1" dockerfile="$ROOT/$1/Dockerfile"
  echo "→ $1/Dockerfile"
  local stage="" line src resolved
  while IFS= read -r line; do
    if [[ "${line^^}" == FROM* ]]; then
      read -ra f <<<"$line"
      stage=""
      for ((i = 1; i < ${#f[@]}; i++)); do
        [[ "${f[i],,}" == as ]] && stage="${f[i + 1]}"
      done
      continue
    fi
    [[ "${line^^}" != COPY* ]] && continue
    while IFS= read -r src; do
      [[ -z "$src" || "$src" == '$'* ]] && continue
      resolved="$dir/$src"
      if [[ -e "$resolved" ]]; then
        note "COPY $src${stage:+ (stage $stage)} ok"
      else
        fail "COPY $src${stage:+ (stage $stage)} — not found at $resolved"
      fi
    done < <(copy_sources "$line")
  done < "$dockerfile"

  if [[ -f "$ROOT/$dir/.dockerignore" ]]; then
    local negations
    negations=$(grep -cE '^!' "$ROOT/$dir/.dockerignore" || true)
    if [[ "${negations:-0}" -eq 0 ]]; then
      note "dockerignore has no '!' rule — a future COPY under an ignored path would ship nothing"
    else
      note "dockerignore: $negations negation rule(s)"
    fi
  else
    fail "no .dockerignore — the build context would include node_modules/.venv"
  fi

  if [[ -f "$ROOT/$dir/package.json" ]]; then
    local defined named
    defined=$(python3 -c "
import json
print(' '.join(json.load(open('$ROOT/$dir/package.json')).get('scripts', {})))")
    # Matches both `CMD npm run start` and `CMD ["npm","run","start",...]`.
    named=$(grep -E '^CMD' "$dockerfile" | tr -d '",[]' | grep -oE 'npm +run +[a-z:-]+' | awk '{print $3}' | sort -u || true)
    for name in $named; do
      if [[ " $defined " == *" $name "* ]]; then
        note "CMD npm run $name — script defined"
      else
        fail "CMD runs 'npm run $name' but package.json has no such script"
      fi
    done
  fi
  echo
}

check_compose() {
  echo "→ infra/docker-compose*.yml"
  local out
  out=$(python3 scripts/_check_compose_contexts.py "$ROOT" 2>&1) || true
  printf '%s\n' "$out" | grep -E '^\s*(ok|FAIL)'
  local n
  n=$(printf '%s\n' "$out" | grep -cE '^\s*FAIL' || true)
  failures=$((failures + n))
  echo
}

# The agent resolves its credential itself, per provider (agent/lib/credentials.ts),
# so compose must not hard-require one with `${VAR:?…}`: that operator cannot be
# conditional on RETRACT_LLM_PROVIDER, and it forced every deployment to invent a
# gateway key the openai provider never reads. A regression here is invisible in the
# app until an agent message fails, so it is checked statically.
check_credential_not_hard_required() {
  echo "→ infra/docker-compose.prod.yml (LLM credential)"
  local file="$ROOT/infra/docker-compose.prod.yml"
  if grep -qE 'AI_GATEWAY_API_KEY:.*\$\{AI_GATEWAY_API_KEY:\?' "$file"; then
    fail "AI_GATEWAY_API_KEY uses \${VAR:?…} — the agent resolves credentials per provider; use \${VAR:-}"
  else
    echo "  ok   AI_GATEWAY_API_KEY is optional (the agent validates per provider)"
  fi
  if ! grep -qE 'RETRACT_API_KEY:.*\$\{RETRACT_API_KEY:-\}' "$file"; then
    fail "RETRACT_API_KEY is not passed through to the agent container — the openai provider needs it"
  else
    echo "  ok   RETRACT_API_KEY is passed through"
  fi
  # The custom-endpoint variables must reach the agent too; without them a container
  # a containerized openai deployment silently ignores RETRACT_LLM_BASE_URL.
  for v in RETRACT_LLM_BASE_URL RETRACT_LLM_API_MODE RETRACT_LLM_API_KEY; do
    if ! grep -qE "$v:.*\\\$\{$v:-" "$file"; then
      fail "$v is not passed through to the agent container"
    else
      echo "  ok   $v is passed through"
    fi
  done
  echo
}

# The agent compiles its provider/model into the image. If those build args are
# dropped, the deployment silently runs whatever the code default is, which is the
# failure mode this whole build-arg path exists to fix.
check_agent_build_wiring() {
  echo "→ agent build inputs"
  local dockerfile="$ROOT/agent/Dockerfile" compose="$ROOT/infra/docker-compose.prod.yml"
  for arg in RETRACT_LLM_PROVIDER RETRACT_MODEL RETRACT_LLM_BASE_URL RETRACT_LLM_API_MODE RETRACT_LLM_HEADERS; do
    if ! grep -qE "^ARG $arg" "$dockerfile"; then
      fail "agent/Dockerfile has no ARG $arg — the compiled manifest cannot be configured"
    elif ! grep -qE "^        $arg:" "$compose"; then
      fail "compose does not pass $arg as an agent build arg"
    else
      echo "  ok   $arg is a build input"
    fi
  done
  if ! grep -qE 'ARG RETRACT_BUILD_API_KEY=' "$dockerfile"; then
    fail "agent/Dockerfile has no non-secret RETRACT_BUILD_API_KEY placeholder"
  elif ! grep -q 'grep -rqF "${RETRACT_BUILD_API_KEY}" .output' "$dockerfile"; then
    fail "agent/Dockerfile does not check .output for the build credential"
  else
    echo "  ok   build credential is a placeholder and the output is checked for it"
  fi
  # A real key must never be a build arg: they are visible in image history.
  if grep -qE 'ARG .*(API_KEY|TOKEN).*=' "$dockerfile" |
    grep -v 'RETRACT_BUILD_API_KEY' >/dev/null; then
    fail "agent/Dockerfile declares a credential-shaped build arg"
  fi
  echo
}

# The API trusts forwarded headers from one network. That network is a deployment
# decision, so it must be fixed in the compose file and passed to both uvicorn and
# the application; otherwise the limiter charges every user to the nginx address.
check_proxy_wiring() {
  echo "→ client-IP trust"
  local compose="$ROOT/infra/docker-compose.prod.yml" nginx="$ROOT/frontend/nginx.conf"
  if ! grep -q 'subnet: 172.28.0.0/16' "$compose"; then
    fail "compose does not pin the default network to 172.28.0.0/16"
  else
    echo "  ok   compose network is pinned to 172.28.0.0/16"
  fi
  if ! grep -q -- '--forwarded-allow-ips=${RETRACT_TRUSTED_PROXY_CIDRS' "$compose"; then
    fail "uvicorn does not receive --forwarded-allow-ips from RETRACT_TRUSTED_PROXY_CIDRS"
  else
    echo "  ok   uvicorn trusts RETRACT_TRUSTED_PROXY_CIDRS"
  fi
  if ! grep -q 'RETRACT_TRUSTED_PROXY_CIDRS:' "$compose"; then
    fail "the API does not receive RETRACT_TRUSTED_PROXY_CIDRS"
  else
    echo "  ok   the API receives the same trusted proxy list"
  fi
  if ! grep -q 'real_ip_header X-Forwarded-For' "$nginx"; then
    fail "nginx does not recover the browser address from Caddy's X-Forwarded-For"
  else
    echo "  ok   nginx uses real_ip from X-Forwarded-For"
  fi
  echo
}

# Budgets are the difference between a public demo and an open invoice. Check that
# each layer is wired, without pretending to prove the provider console setting.
check_budget_wiring() {
  echo "→ LLM budget wiring"
  local compose="$ROOT/infra/docker-compose.prod.yml" example="$ROOT/.env.example"
  for v in RETRACT_DEMO_LLM_BUDGET_USD RETRACT_USER_LLM_BUDGET_USD RETRACT_GLOBAL_LLM_BUDGET_USD; do
    if ! grep -qE "$v:" "$compose"; then
      fail "$v is not passed to the API"
    elif ! grep -qE "^$v=" "$example"; then
      fail "$v is missing from .env.example"
    else
      echo "  ok   $v is documented and passed"
    fi
  done
  for v in RETRACT_LLM_INPUT_COST_PER_MTOK RETRACT_LLM_OUTPUT_COST_PER_MTOK; do
    if ! grep -qE "$v:" "$compose"; then
      fail "$v is not passed to the agent — token-priced providers cannot be metered"
    elif ! grep -qE "^$v=" "$example"; then
      fail "$v is missing from .env.example"
    else
      echo "  ok   $v is documented and passed"
    fi
  done
  for v in RETRACT_AGENT_MAX_INPUT_TOKENS RETRACT_AGENT_MAX_OUTPUT_TOKENS RETRACT_AGENT_MAX_COST_USD; do
    if [[ $(grep -cE "$v" "$compose") -lt 2 ]]; then
      fail "$v must reach the agent as both a build arg and a runtime value"
    else
      echo "  ok   $v reaches the build and runtime"
    fi
  done
  echo
}

# `docker compose config` catches duplicate keys, unresolved anchors, and required
# variables the runtime would discover only on the deployment host.
check_prod_compose_config() {
  echo "→ docker compose config"
  if ! command -v docker >/dev/null 2>&1 || ! docker compose version >/dev/null 2>&1; then
    note "docker compose is unavailable; skipped"
    echo
    return
  fi
  local env_file
  env_file=$(mktemp)
  cat >"$env_file" <<'EOF'
POSTGRES_USER=retract
POSTGRES_PASSWORD=static-check-password
POSTGRES_DB=ai_intel
RETRACT_JWT_SECRET=static-check-jwt-secret-at-least-32-bytes-long
RETRACT_AGENT_TOKEN=static-check-agent-service-token
PUBLIC_URL=https://retract.example
EOF
  local output
  if output=$(docker compose --env-file "$env_file" -f "$ROOT/infra/docker-compose.prod.yml" config -q 2>&1); then
    note "compose config resolves"
  else
    fail "docker compose config failed: $output"
  fi
  rm -f "$env_file"
  echo
}

# The Oracle free tier is arm64, and the old image fetched only the x64 gitleaks
# asset, so the build succeeded nowhere the target actually was. Check the selected
# asset is architecture-aware and checksum-pinned.
check_backend_architecture() {
  echo "→ backend image architecture"
  local dockerfile="$ROOT/backend/Dockerfile"
  if ! grep -q '^ARG TARGETARCH' "$dockerfile"; then
    fail "backend/Dockerfile does not select an asset from TARGETARCH"
  else
    echo "  ok   gitleaks asset is selected from TARGETARCH"
  fi
  if ! grep -q 'GITLEAKS_SHA256_X64=' "$dockerfile" ||
    ! grep -q 'GITLEAKS_SHA256_ARM64=' "$dockerfile"; then
    fail "backend/Dockerfile does not pin a checksum for both architectures"
  else
    echo "  ok   both architecture checksums are pinned"
  fi
  echo
}

echo "Container configuration check"
echo
for dir in backend frontend agent; do
  check_dockerfile "$dir"
done
check_compose
check_credential_not_hard_required
check_agent_build_wiring
check_backend_architecture
check_proxy_wiring
check_budget_wiring
check_prod_compose_config

if [[ "$failures" -gt 0 ]]; then
  echo "$failures problem(s) found"
  exit 1
fi
echo "All static container checks passed."
echo "This does not prove the images build. To do that:"
echo "  docker compose -f infra/docker-compose.prod.yml build"
