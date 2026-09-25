# Research Basis

This document maps each design decision in `implementation.md` (section 0) to the
research it is grounded in.

| Decision | Paper / Source | What it says | How it shapes this platform |
|----------|----------------|--------------|-----------------------------|
| D1 — Deterministic-first, LLM-second | *Large Language Models Versus Static Code Analysis Tools: A Systematic Benchmark for Vulnerability Detection* (arXiv:2508.04448) | LLMs beat SonarQube/CodeQL/Snyk on F1 (0.79 vs 0.26–0.55) but with more false positives and imprecise line localization. Authors recommend a hybrid pipeline. | Real tools (Semgrep, gitleaks, OSV, radon, coverage) run first; LLM agents triage and reason on top of tool output. |
| D2 — Verdict schema with verified/hypothesis status | *Towards Verified Code Reasoning by LLMs* (arXiv:2509.26546); *VerifiAgent* (EMNLP 2025 Findings) | LLM code-reasoning answers can be validated by extracting formal representations and checking them with program-analysis tools; a two-layer verification agent catches wrong judgments. | Every finding carries `{claim, evidence, file:line, verifier, confidence, status}`. Tool-confirmed → `verified`; LLM-only → `hypothesis`. |
| D3 — Repo knowledge graph (not flat RAG) | *RANGER* (arXiv:2509.25257); *CodeX Graph* (NAACL 2025); *RepoFormer* (arXiv:2403.10059) | Graph-enhanced retrieval over repository structure beats flat embedding RAG on cross-file tasks; always-retrieve can hurt — retrieval should be selective. | We build a symbol/import/call graph (Postgres). The agent's tools are graph queries (`callers`, `callees`, `dependents`, `path`, `neighborhood`, `find_symbols`) plus `read_source` for exact lines. |
| D4 — LLM never infers structure | *Do Code LLMs Do Static Analysis?* (arXiv:2505.12118) | Code LLMs perform poorly on callgraph/AST/dataflow tasks. | All structural facts come from tree-sitter parsing and tool output; agents receive them as given context. |
| D5 — Calibrated confidence + human approval | *Overconfident and Unconfident AI Hinder Human-AI Collaboration* (arXiv:2402.07632); *Investigating and Designing for Trust in AI-powered Code Generation Tools* (FAccT 2024) | Uncalibrated confidence degrades human-AI collaboration; developers want confidence signals, acceptance-rate stats, and low-confidence highlighting. | Confidence = self-consistency + cross-tool agreement; high-severity hypotheses require approve/dismiss; per-category acceptance rates shown in UI. |
| D6 — Per-function chunked vulnerability analysis | *Beyond Single Bugs: Benchmarking LLMs for Multi-Vulnerability Detection* (arXiv:2512.22306) | LLM recall collapses (<0.30) on dense multi-vulnerability files. | Security agent analyzes functions/chunks with caller-callee context, never whole files at once. |
| D7 — Test agent reports gaps and plans | *TestGenEval* (ICLR 2025); *CoverUp* (arXiv:2403.16218); *Panta* (arXiv:2503.13580) | Best LLMs reach only ~35% coverage on real repos; coverage-guided iterative loops improve this substantially. | Test agent consumes real coverage data and produces prioritized test plans instead of untrusted generated tests. |
| D8 — Honest scoring | Trust-calibration literature (D5 sources) | Users must be able to calibrate trust; scores derived from unverified claims should be discounted. | Pillar scores weight verified findings fully, hypotheses at 0.5, dismissed at 0. |
| D9 — Benchmark harness | *JITVUL* (ACL 2025) | Pairwise vulnerability-introducing/fixing commits enable realistic evaluation of detection methods. | `benchmark/` contains seedy repos with ground truth and computes precision/recall per pillar. |
| D10 — eve as the agent runtime | [eve.dev](https://eve.dev) documentation (agent definitions, typed tools, HITL approval policies, subagents, evals) | Tool schemas, approval gates, durable sessions, and eval harnesses are framework concerns, not product concerns; they are also where a hand-rolled agent layer is least differentiated. | The agent lives in `agent/` (Node 24): typed tools, `approval: always()` on the two actions a human must own, five subagents, and `eve eval` for behaviour tests. |
| D11 — No embeddings (revised D3) | Same graph-retrieval sources as D3, read as a *removal* result | The graph plus exact source reading answered the questions the embedding index was retrieved for; the index only added drift risk (embeddings of a commit that no longer matches the analysed tree) and operational surface (pgvector, chunker, a second migration). | Removed `chunks`, the chunker, the embedding providers, `/search`, and the Explore search box. `agent/evals/no-rag/no-search-endpoint.eval.ts` fails the build if a retrieval endpoint is ever reintroduced. |

## Additional references

- *AI-powered Code Review with LLMs: Early Results* (arXiv:2404.18496) — multi-agent code review design.
- *CodeAgent: Autonomous Communicative Agents for Code Review* (EMNLP 2024) — multi-agent review with a QA-checker supervisor.
- *Evaluation and Benchmarking of LLM Agents: A Survey* (KDD 2025) — agent evaluation taxonomy.
- *Assessing the Quality and Security of AI-Generated Code* (arXiv:2508.14727) — even passing LLM code averages 1.45–1.77 static-analysis issues; motivates always-on static analysis.
- *Retrieval-Augmented Code Generation: A Survey with Focus on Repository-Level Approaches* (arXiv:2510.04905) — repo-level RAG landscape. Read as the counterfactual for D11: it catalogues what embedding-based repo retrieval buys, which is the bar the symbol graph has to clear without it.

## Where the plan changed during the build

Two decisions were revised by what the code actually needed, and the reasoning is
kept here rather than quietly dropped:

- **D3 → D11 (no RAG).** The embedding index was built and used during Phase 3,
  then removed once the graph tools and `read_source` existed. The agent cites
  `file:line` it has read, so there is no index to keep in sync with the analysed
  commit, and no second source of retrieval truth that can disagree with the code.
- **D10 (eve).** The original Phase 4 built five Python agents against an
  OpenAI-compatible adapter. That layer owned schema validation, repair retries,
  cost accounting, and a mock harness — all of it framework plumbing. eve supplies
  the same guarantees with typed tool schemas, approval policies, subagents, and a
  hermetic eval runner, so the work went into the trust layer (D5, D8) and the
  benchmark instead.
