#!/usr/bin/env bash
# Static checks for the retract skill. Runs in CI, needs no network and no daemon.
#
# Catches:
#   * a scoring.md that quotes a constant scoring.py no longer has
#   * a category the skill's playbook forgot
#   * skill frontmatter that the skills CLI would reject
#
# The skill quotes Retract's scoring model to coding agents; when the curve is
# retuned the docs must move with it, and nothing else will notice.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

fails=0
record() { if [ "$1" -ne 0 ]; then fails=$((fails + 1)); fi; }

echo "→ skills/retract (frontmatter)"
# The skills CLI requires name and description; the name must match the folder.
python3 - "$ROOT/skills/retract/SKILL.md" <<'EOF'
import pathlib, re, sys
skill = pathlib.Path(sys.argv[1]).read_text()
match = re.match(r"^---\n(.*?)\n---\n", skill, re.DOTALL)
frontmatter = match.group(1) if match else ""
name = re.search(r"^name:\s*(\S+)", frontmatter, re.MULTILINE)
description = re.search(r"^description:\s*\S", frontmatter, re.MULTILINE)
ok = True
if not name or name.group(1) != "retract":
    print("   FAIL name must be 'retract' to match the folder"); ok = False
if not description:
    print("   FAIL description is required by the skills CLI"); ok = False
if not ok or name:
    print(f"   ok   name: {name.group(1) if name else 'missing'}")
sys.exit(0 if ok else 1)
EOF
record $?

echo "→ skills/retract/references (vs backend/app/analysis_engine/scoring.py)"
out=$(python3 scripts/_check_skill_constants.py "$ROOT" 2>&1) || record 1
echo "$out"

echo "→ referenced files exist"
for file in $(grep -rIoE "references/[a-z-]+\.md" "$ROOT/skills/retract/SKILL.md" | sort -u); do
  if [ -f "$ROOT/skills/retract/$file" ]; then
    echo "   ok   $file"
  else
    echo "   FAIL $file referenced from SKILL.md but missing"; record 1
  fi
done

if [ "$fails" -eq 0 ]; then
  echo "All skill checks passed."
else
  echo "$fails check(s) failed."
  exit 1
fi
