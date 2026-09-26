"""Benchmark CLI: score an existing analysis against a repository's ground truth.

    python -m app.benchmark --repo seedy-python-app
    python -m app.benchmark --repo seedy-python-app --analysis-id 18 --stdout

Reads the findings already stored for an analysis, so it never re-runs the
analyzers and needs no external tools.

Ground truth is expected at ``benchmark/ground-truth/<repo>.yaml`` relative to the
repository root; override with ``--ground-truth``.
"""

import argparse
import sys
from pathlib import Path

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.benchmark.ground_truth import GroundTruthError, load_ground_truth
from app.benchmark.match import score_findings
from app.benchmark.report import render_report
from app.db import get_session_factory
from app.models import Analysis, Finding, Repository

REPO_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_GROUND_TRUTH_DIR = REPO_ROOT / "benchmark" / "ground-truth"


class RepoNotFound(LookupError):
    """No tracked repository matches the requested name."""


def _latest_analysis(session: Session, repo_name: str) -> Analysis:
    _owner, _slash, bare_name = repo_name.rpartition("/")
    repo = session.scalar(
        select(Repository).where(
            or_(
                (Repository.owner + "/" + Repository.name) == repo_name,
                Repository.name == bare_name,
            )
        )
    )
    if repo is None:
        raise RepoNotFound(repo_name)
    analysis = session.scalar(
        select(Analysis)
        .where(Analysis.repository_id == repo.id)
        .order_by(Analysis.id.desc())
        .limit(1)
    )
    if analysis is None:
        raise LookupError(f"repository {repo_name} has no analysis yet; run one first")
    return analysis


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="app.benchmark", description=__doc__)
    parser.add_argument("--repo", help="Repository as owner/name, or just name")
    parser.add_argument("--analysis-id", type=int, help="Score this analysis instead of the latest")
    parser.add_argument(
        "--ground-truth",
        type=Path,
        help="Ground-truth YAML (default: benchmark/ground-truth/<repo>.yaml)",
    )
    parser.add_argument(
        "--out",
        type=Path,
        help="Write the Markdown report here (default: benchmark/REPORT.md, skipped with --stdout)",
    )
    parser.add_argument(
        "--stdout", action="store_true", help="Print the report instead of writing it"
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if not args.repo and not args.analysis_id:
        print("error: pass --repo or --analysis-id", file=sys.stderr)
        return 2

    session = get_session_factory()()
    try:
        if args.analysis_id:
            analysis = session.get(Analysis, args.analysis_id)
            if analysis is None:
                print(f"error: analysis {args.analysis_id} not found", file=sys.stderr)
                return 2
        else:
            try:
                analysis = _latest_analysis(session, args.repo)
            except (RepoNotFound, LookupError) as exc:
                print(f"error: {exc}", file=sys.stderr)
                return 2

        truth_path = args.ground_truth or (
            DEFAULT_GROUND_TRUTH_DIR / f"{analysis.repository.name}.yaml"
        )
        try:
            truth = load_ground_truth(truth_path)
        except GroundTruthError as exc:
            print(f"error: {exc}", file=sys.stderr)
            return 2

        findings = list(session.scalars(select(Finding).where(Finding.analysis_id == analysis.id)))
        result = score_findings(truth, findings, analysis.id)

        command = (
            f"cd backend && python -m app.benchmark --repo {truth.repo} --analysis-id {analysis.id}"
        )
        report = render_report(result, command=command)
        if args.stdout:
            print(report)
        else:
            out_path = args.out or (REPO_ROOT / "benchmark" / "REPORT.md")
            out_path.parent.mkdir(parents=True, exist_ok=True)
            out_path.write_text(report)
            print(f"wrote {out_path}")
            print(
                f"recall={result.recall:.2f} precision(grounded)="
                f"{result.precision_grounded:.2f} f1={result.f1_grounded:.2f}"
                if result.recall is not None and result.precision_grounded is not None
                else "no findings to score"
            )
        return 0
    finally:
        session.close()


if __name__ == "__main__":
    raise SystemExit(main())
