"""Assert the retract skill's reference docs still match the scoring source.

Extracted from ``verify-skill.sh`` so the shell script stays readable.

The skill teaches coding agents Retract's scoring model. The curve has been
retuned twice already (250 → 100 → 30), so a stale skill would silently
instruct agents to optimise against a dead formula. This file parses
``scoring.py`` with ``ast`` — the source is the truth, never this script —
and checks each constant appears in ``skills/retract/references/scoring.md``,
and each scored category in ``categories.md``.

Reports one line per check; the caller counts the ``FAIL`` lines.
"""

import ast
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
SCORING = ROOT / "backend" / "app" / "analysis_engine" / "scoring.py"
SKILL = ROOT / "skills" / "retract"


def _value_of(tree: ast.Module, name: str):
    for node in tree.body:
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id == name:
                    return node.value
        if isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            if node.target.id == name:
                return node.value
    return None


def _int_dict(node) -> dict[str, object]:
    return {
        k.value: ast.literal_eval(v)
        for k, v in zip(node.keys, node.values)
        if isinstance(k, ast.Constant)
    }


def _attr_or_value(node) -> object:
    # STATUS_FACTOR keys are FindingStatus.VERIFIED etc.; take the attribute name.
    if isinstance(node, ast.Attribute):
        return node.attr.lower()
    return ast.literal_eval(node)


def main() -> int:
    scoring_text = SCORING.read_text()
    tree = ast.parse(scoring_text)

    severity: dict = _int_dict(_value_of(tree, "SEVERITY_WEIGHT"))
    status: dict = _int_dict(_value_of(tree, "STATUS_FACTOR"))
    weights: dict = _int_dict(_value_of(tree, "PILLAR_WEIGHTS"))
    categories: dict = _int_dict(_value_of(tree, "CATEGORY_PILLAR"))
    constants: dict[str, float] = {}
    for name in (
        "HALF_SCORE_DENSITY",
        "WORST_PILLAR_HEADROOM",
        "MIN_KLOC",
        "COUNT_HALF_SCORE_PENALTY",
    ):
        constants[name] = ast.literal_eval(_value_of(tree, name))

    scoring_md = (SKILL / "references" / "scoring.md").read_text()
    categories_md = (SKILL / "references" / "categories.md").read_text()

    failures = 0

    def check(ok: bool, label: str) -> None:
        nonlocal failures
        print(f"   {'ok  ' if ok else 'FAIL'} {label}")
        if not ok:
            failures += 1

    def forms(value) -> set[str]:
        """The ways the same number may legitimately be written."""
        return {f"{value:g}", f"{float(value):.2f}", f"{float(value):.1f}"}

    def quoted(value) -> bool:
        return any(f"**{form}**" in scoring_md for form in forms(value))

    for name, value in severity.items():
        check(quoted(value), f"severity {name}={value:g} quoted")
    for name, value in status.items():
        check(quoted(value), f"status {name}={value:g} quoted")
    for name, value in weights.items():
        check(quoted(value), f"pillar weight {name}={value:g} quoted")
    for name, value in constants.items():
        check(quoted(value), f"constant {name}={value:g} quoted")

    scored = [c for c, pillar in categories.items() if pillar is not None]
    unscored = [c for c, pillar in categories.items() if pillar is None]
    for category in scored:
        check(f"`{category}`" in categories_md, f"scored category {category} documented")
    check("not in `CATEGORY_PILLAR`" in categories_md, "unscored categories documented")
    for category in unscored:
        check(category in categories_md, f"unscored category {category} documented")

    # The formula the skill teaches must be the formula in the source.
    check(
        "worst_pillar + 15" in scoring_md and "WORST_PILLAR_HEADROOM" in scoring_md,
        "worst-pillar cap described",
    )
    check("penalty per KLOC" in scoring_md or "per KLOC" in scoring_md, "density basis described")

    print(f"{'all skill/scoring checks passed' if failures == 0 else f'{failures} FAIL lines'}")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
