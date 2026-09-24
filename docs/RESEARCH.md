# Research Basis

This document maps each design decision in `implementation.md` (section 0) to the
research it is grounded in.

| Decision | Paper / Source | What it says | How it shapes this platform |
|----------|----------------|--------------|-----------------------------|
| D1 — Deterministic-first, LLM-second | *Large Language Models Versus Static Code Analysis Tools: A Systematic Benchmark for Vulnerability Detection* (arXiv:2508.04448) | LLMs beat SonarQube/CodeQL/Snyk on F1 (0.79 vs 0.26–0.55) but with more false positives and imprecise line localization. Authors recommend a hybrid pipeline. | Real tools (Semgrep, gitleaks, OSV, radon, coverage) run first; LLM agents triage and reason on top of tool output. |
| D2 — Verdict schema with verified/hypothesis status | *Towards Verified Code Reasoning by LLMs* (arXiv:2509.26546); *VerifiAgent* (EMNLP 2025 Findings) | LLM code-reasoning answers can be validated by extracting formal representations and checking them with program-analysis tools; a two-layer verification agent catches wrong judgments. | Every finding carries `{claim, evidence, file:line, verifier, confidence, status}`. Tool-confirmed → `verified`; LLM-only → `hypothesis`. |
| D3 — Repo knowledge graph + selective retrieval | *RANGER* (arXiv:2509.25257); *CodeX Graph* (NAACL 2025); *RepoFormer* (arXiv:2403.10059) | Graph-enhanced retrieval over repository structure beats flat embedding RAG on cross-file tasks; always-retrieve can hurt — retrieval should be selective. | We build a symbol/import/call graph (Postgres) plus pgvector embeddings, with a heuristic gate that prefers graph lookups for structural questions. |
| D4 — LLM never infers structure | *Do Code LLMs Do Static Analysis?* (arXiv:2505.12118) | Code LLMs perform poorly on callgraph/AST/dataflow tasks. | All structural facts come from tree-sitter parsing and tool output; agents receive them as given context. |
| D5 — Calibrated confidence + human approval | *Overconfident and Unconfident AI Hinder Human-AI Collaboration* (arXiv:2402.07632); *Investigating and Designing for Trust in AI-powered Code Generation Tools* (FAccT 2024) | Uncalibrated confidence degrades human-AI collaboration; developers want confidence signals, acceptance-rate stats, and low-confidence highlighting. | Confidence = self-consistency + cross-tool agreement; high-severity hypotheses require approve/dismiss; per-category acceptance rates shown in UI. |
| D6 — Per-function chunked vulnerability analysis | *Beyond Single Bugs: Benchmarking LLMs for Multi-Vulnerability Detection* (arXiv:2512.22306) | LLM recall collapses (<0.30) on dense multi-vulnerability files. | Security agent analyzes functions/chunks with caller-callee context, never whole files at once. |
| D7 — Test agent reports gaps and plans | *TestGenEval* (ICLR 2025); *CoverUp* (arXiv:2403.16218); *Panta* (arXiv:2503.13580) | Best LLMs reach only ~35% coverage on real repos; coverage-guided iterative loops improve this substantially. | Test agent consumes real coverage data and produces prioritized test plans instead of untrusted generated tests. |
| D8 — Honest scoring | Trust-calibration literature (D5 sources) | Users must be able to calibrate trust; scores derived from unverified claims should be discounted. | Pillar scores weight verified findings fully, hypotheses at 0.5, dismissed at 0. |
| D9 — Benchmark harness | *JITVUL* (ACL 2025) | Pairwise vulnerability-introducing/fixing commits enable realistic evaluation of detection methods. | `benchmark/` contains seedy repos with ground truth and computes precision/recall per pillar. |

## Additional references

- *AI-powered Code Review with LLMs: Early Results* (arXiv:2404.18496) — multi-agent code review design.
- *CodeAgent: Autonomous Communicative Agents for Code Review* (EMNLP 2024) — multi-agent review with a QA-checker supervisor.
- *Evaluation and Benchmarking of LLM Agents: A Survey* (KDD 2025) — agent evaluation taxonomy.
- *Assessing the Quality and Security of AI-Generated Code* (arXiv:2508.14727) — even passing LLM code averages 1.45–1.77 static-analysis issues; motivates always-on static analysis.
- *Retrieval-Augmented Code Generation: A Survey with Focus on Repository-Level Approaches* (arXiv:2510.04905) — repo-level RAG landscape.
