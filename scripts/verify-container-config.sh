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
# conditional on AI_INTEL_LLM_PROVIDER, and it forced every deployment to invent a
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
  if ! grep -qE 'AI_INTEL_API_KEY:.*\$\{AI_INTEL_API_KEY:-\}' "$file"; then
    fail "AI_INTEL_API_KEY is not passed through to the agent container — the openai provider needs it"
  else
    echo "  ok   AI_INTEL_API_KEY is passed through"
  fi
  # The custom-endpoint variables must reach the agent too; without them a container
  # a containerized openai deployment silently ignores AI_INTEL_LLM_BASE_URL.
  for v in AI_INTEL_LLM_BASE_URL AI_INTEL_LLM_API_MODE AI_INTEL_LLM_API_KEY; do
    if ! grep -qE "$v:.*\\\$\{$v:-" "$file"; then
      fail "$v is not passed through to the agent container"
    else
      echo "  ok   $v is passed through"
    fi
  done
  echo
}

echo "Container configuration check"
echo
for dir in backend frontend agent; do
  check_dockerfile "$dir"
done
check_compose
check_credential_not_hard_required

if [[ "$failures" -gt 0 ]]; then
  echo "$failures problem(s) found"
  exit 1
fi
echo "All static container checks passed."
echo "This does not prove the images build. To do that:"
echo "  docker compose -f infra/docker-compose.prod.yml build"
