#!/usr/bin/env bash
# Fail if a model credential was compiled into the agent image output.
#
# eve compiles the resolved model into .output, and the agent module is imported at
# build time to do it. The credential is not supposed to be serialized, but that is
# an implementation detail of the current eve version, not a promise: this check is
# the gate that keeps a rebuild from shipping a key in a public image.
#
#   scripts/verify-agent-build.sh [agent-directory]
#
# Reads candidate keys from the environment (the names the agent accepts) and scans
# every byte under .output. It never prints a key.
set -euo pipefail

AGENT_DIR="${1:-agent}"
OUTPUT="$AGENT_DIR/.output"

if [ ! -d "$OUTPUT" ]; then
  echo "no build output at $OUTPUT; run 'npm run build' in $AGENT_DIR first" >&2
  exit 1
fi

python3 - "$OUTPUT" <<'PY'
import os
import sys
from pathlib import Path

output = Path(sys.argv[1])
variables = (
    "RETRACT_LLM_API_KEY",
    "RETRACT_API_KEY",
    "OPENAI_API_KEY",
    "AI_GATEWAY_API_KEY",
    "RETRACT_BUILD_API_KEY",
)
keys = []
for name in variables:
    value = os.environ.get(name, "").strip()
    # Short values colliding with ordinary text would make this check noisy; a real
    # key is much longer than this.
    if len(value) >= 16:
        keys.append((name, value))

if not keys:
    print("verify-agent-build: no credential in the environment to check")
    sys.exit(0)

hits = []
for root, _dirs, files in os.walk(output):
    for filename in files:
        path = Path(root) / filename
        try:
            data = path.read_bytes()
        except OSError:
            continue
        for name, value in keys:
            if value.encode() in data:
                hits.append((str(path), name))

if hits:
    for path, name in hits:
        print(f"credential {name} found in {path}", file=sys.stderr)
    print("refusing to ship an agent image with a compiled credential", file=sys.stderr)
    sys.exit(1)

print(f"verify-agent-build: scanned {output} for {len(keys)} credential(s); none found")
PY
