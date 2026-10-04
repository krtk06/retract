"""Validate compose build contexts and build targets.

Extracted from ``verify-container-config.sh`` so the shell script stays readable.
Reports one line per check; the caller counts the ``FAIL`` lines.
"""

import pathlib
import re
import sys


def stages_in(dockerfile: pathlib.Path) -> list[str]:
    """Stage names in file order. Order matters: the *last* stage is the implicit
    default that `docker build` uses when no `--target` is given."""
    stages: list[str] = []
    for line in dockerfile.read_text().splitlines():
        parts = line.split()
        if not parts or parts[0].upper() != "FROM":
            continue
        lowered = [p.lower() for p in parts]
        if "as" in lowered:
            name = parts[lowered.index("as") + 1]
            if name not in stages:
                stages.append(name)
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

            dockerfile = context / "Dockerfile"
            if not dockerfile.is_file():
                if target is not None:
                    print(f"   FAIL {compose_file.name}:{name} names a target but has no Dockerfile")
                continue

            stages = stages_in(dockerfile)

            if target is None:
                # A multi-stage build with no target silently resolves to the last
                # stage in the file. That is a real hazard: `dev` was once the last
                # stage of frontend/Dockerfile, so docker-compose.prod.yml shipped
                # the Vite dev server and published host :80 to a container
                # serving :5173. Require the target to be written down.
                if len(stages) > 1:
                    print(
                        f"   FAIL {compose_file.name}:{name} builds a multi-stage Dockerfile "
                        f"with no target; the implicit default is the last stage "
                        f"({stages[-1]}), which is silent to reorder"
                    )
                else:
                    print(f"   ok   {compose_file.name}:{name} single-stage build, no target needed")
                continue

            if target.group(1) in stages:
                print(f"   ok   {compose_file.name}:{name} build target {target.group(1)}")
            else:
                print(
                    f"   FAIL {compose_file.name}:{name} build target {target.group(1)} "
                    f"is not a stage; declared: {stages or 'none'}"
                )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())