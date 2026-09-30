"""Validate compose build contexts and build targets.

Extracted from ``verify-container-config.sh`` so the shell script stays readable.
Reports one line per check; the caller counts the ``FAIL`` lines.
"""

import pathlib
import re
import sys


def stages_in(dockerfile: pathlib.Path) -> set[str]:
    stages: set[str] = set()
    for line in dockerfile.read_text().splitlines():
        parts = line.split()
        if not parts or parts[0].upper() != "FROM":
            continue
        lowered = [p.lower() for p in parts]
        if "as" in lowered:
            stages.add(parts[lowered.index("as") + 1])
    return stages


def main() -> int:
    root = pathlib.Path(sys.argv[1])
    for compose_file in sorted((root / "infra").glob("docker-compose*.yml")):
        for block in re.split(r"\n  (?=\w)", compose_file.read_text()):
            name = block.split(":", 1)[0].strip()
            # Two forms are in use:
            #   build: ../dir                          (short)
            #   build:                                 (long, keys on following lines)
            #     context: ../dir
            #     target: dev
            # `[ \t]` rather than `\s` so a bare `build:` cannot swallow the next
            # key by matching across the newline.
            inline = re.search(r"[ \t]build:[ \t]*(\S+)", block)
            longform = re.search(r"[ \t]context:[ \t]*(\S+)", block)
            target = re.search(r"[ \t]target:[ \t]*(\S+)", block)
            match = inline or longform
            if not match:
                continue
            context = (compose_file.parent / match.group(1)).resolve()
            if not context.is_dir():
                print(f"   FAIL {compose_file.name}:{name} build context {match.group(1)} (missing)")
                continue
            print(f"   ok   {compose_file.name}:{name} build context {match.group(1)}")
            if target is None:
                continue
            dockerfile = context / "Dockerfile"
            if not dockerfile.is_file():
                print(f"   FAIL {compose_file.name}:{name} has no Dockerfile in context")
                continue
            stages = stages_in(dockerfile)
            if target.group(1) in stages:
                print(f"   ok   {compose_file.name}:{name} build target {target.group(1)}")
            else:
                print(
                    f"   FAIL {compose_file.name}:{name} build target {target.group(1)} "
                    f"is not a stage; declared: {sorted(stages) or 'none'}"
                )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
