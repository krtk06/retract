"""Assert the retract skill's reference docs still match the sources they quote.

Extracted from ``verify-skill.sh`` so the shell script stays readable.

The skill teaches coding agents Retract's scoring model and its analyzers. The
curve has been retuned twice already (250 → 100 → 30), so a stale skill would
silently instruct agents to optimise against a dead formula. This file parses
``scoring.py`` and the tool runners with ``ast`` — the sources are the truth,
never this script — and checks that each constant and flag the skill quotes
still exists there, and each scored category in ``categories.md``.

That second half exists because dogfooding the skill found the first defect of
this class: ``references/verification.md`` claimed gitleaks "re-scans history
and tree", so an agent following it advised a destructive history rewrite to
clear a secret finding. Retract runs gitleaks with ``--no-git``. A claim about
behaviour is as driftable as a number, so it gets the same treatment.

Reports one line per check; the caller counts the ``FAIL`` lines.
"""

import ast
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
SCORING = ROOT / "backend" / "app" / "analysis_engine" / "scoring.py"
TOOLS = ROOT / "backend" / "app" / "services" / "tools"
SKILL = ROOT / "skills" / "retract"


def _value_of(tree: ast.Module, name: str):
    for node in tree.body:
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id == name:
                    return node.value
        if (
            isinstance(node, ast.AnnAssign)
            and isinstance(node.target, ast.Name)
            and node.target.id == name
        ):
            return node.value
    return None


def _int_dict(node) -> dict[str, object]:
    return {
        k.value: ast.literal_eval(v)
        for k, v in zip(node.keys, node.values, strict=True)
        if isinstance(k, ast.Constant)
    }


def _attr_or_value(node) -> object:
    # STATUS_FACTOR keys are FindingStatus.VERIFIED etc.; take the attribute name.
    if isinstance(node, ast.Attribute):
        return node.attr.lower()
    return ast.literal_eval(node)


def _load_values(tree: ast.Module) -> dict:
    """Every constant the skill quotes, read from the scoring source."""
    constants = {}
    for name in (
        "HALF_SCORE_DENSITY",
        "WORST_PILLAR_HEADROOM",
        "MIN_KLOC",
        "COUNT_HALF_SCORE_PENALTY",
    ):
        constants[name] = ast.literal_eval(_value_of(tree, name))
    return {
        "severity": _int_dict(_value_of(tree, "SEVERITY_WEIGHT")),
        "status": _int_dict(_value_of(tree, "STATUS_FACTOR")),
        "weights": _int_dict(_value_of(tree, "PILLAR_WEIGHTS")),
        "categories": _int_dict(_value_of(tree, "CATEGORY_PILLAR")),
        "constants": constants,
    }


def _check_numbers(check, values: dict, scoring_md: str) -> None:
    """Every number the skill states must appear as written in the scoring table."""

    def forms(value) -> set[str]:
        """The ways the same number may legitimately be written."""
        return {f"{value:g}", f"{float(value):.2f}", f"{float(value):.1f}"}

    def quoted(value) -> bool:
        return any(f"**{form}**" in scoring_md for form in forms(value))

    for group, label in (
        ("severity", "severity"),
        ("status", "status"),
        ("weights", "pillar weight"),
        ("constants", "constant"),
    ):
        for name, value in values[group].items():
            check(quoted(value), f"{label} {name}={value:g} quoted")


def _check_categories(check, categories: dict[str, object], categories_md: str) -> None:
    """Every scored category is documented; every unscored one is named as such."""
    scored = [c for c, pillar in categories.items() if pillar is not None]
    unscored = [c for c, pillar in categories.items() if pillar is None]
    for category in scored:
        check(
            f"`{category}`" in categories_md, f"scored category {category} documented"
        )
    check("not in `CATEGORY_PILLAR`" in categories_md, "unscored categories documented")
    for category in unscored:
        check(category in categories_md, f"unscored category {category} documented")


def _check_thresholds(check, both_refs: str) -> None:
    """Each tool threshold is matched in context, beside the word the doc uses."""

    def tool_constant(module: str, name: str):
        return ast.literal_eval(
            _value_of(ast.parse((TOOLS / module).read_text()), name)
        )

    thresholds = [
        (
            "complexity",
            "CC_MEDIUM",
            "radon complexity medium",
            r"complexity[^\n]*?\b{v}\b",
        ),
        (
            "complexity",
            "CC_HIGH",
            "radon complexity high",
            r"complexity[^\n]*?\b{v}\b = high|high[^\n]*?\b{v}\b",
        ),
        (
            "complexity",
            "MI_LOW",
            "radon maintainability floor",
            r"maintainability[^\n]*?\b{v}\b",
        ),
        (
            "duplication",
            "MIN_WINDOW_LEN",
            "duplication window length",
            r"\b{v}\b normalized",
        ),
        (
            "architecture",
            "FAN_IN_FLOOR",
            "god-module fan-in floor",
            r"fan-in[^\n]*?\b{v}\b",
        ),
    ]
    for module, name, label, pattern in thresholds:
        value = tool_constant(f"{module}.py", name)
        rendered = f"{value:g}"
        ok = re.search(pattern.format(v=rendered), both_refs, re.IGNORECASE) is not None
        check(ok, f"{label} {rendered} quoted in context")


def _check_behaviour_claims(check, both_refs: str, verification_md: str) -> None:
    """Flags the skill asserts about tool behaviour must match the sources."""
    docs_src = (TOOLS / "docs.py").read_text()
    check(
        "< 0.5" in docs_src and ("< 50%" in both_refs or "50%" in both_refs),
        "docstring coverage threshold quoted",
    )
    gitleaks_src = (TOOLS / "gitleaks.py").read_text()
    check(
        "--no-git" in gitleaks_src and "--no-git" in verification_md,
        "gitleaks --no-git (tree, not history) asserted in both",
    )


def main() -> int:
    tree = ast.parse(SCORING.read_text())
    values = _load_values(tree)
    scoring_md = (SKILL / "references" / "scoring.md").read_text()
    categories_md = (SKILL / "references" / "categories.md").read_text()
    verification_md = (SKILL / "references" / "verification.md").read_text()

    failures = 0

    def check(ok: bool, label: str) -> None:
        nonlocal failures
        print(f"   {'ok  ' if ok else 'FAIL'} {label}")
        if not ok:
            failures += 1

    _check_numbers(check, values, scoring_md)
    _check_categories(check, values["categories"], categories_md)
    both_refs = categories_md + verification_md
    _check_thresholds(check, both_refs)

    # The formula the skill teaches must be the formula in the source.
    check(
        "worst_pillar + 15" in scoring_md and "WORST_PILLAR_HEADROOM" in scoring_md,
        "worst-pillar cap described",
    )
    check(
        "penalty per KLOC" in scoring_md or "per KLOC" in scoring_md,
        "density basis described",
    )
    _check_behaviour_claims(check, both_refs, verification_md)

    print(
        f"{'all skill/scoring checks passed' if failures == 0 else f'{failures} FAIL lines'}"
    )
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
