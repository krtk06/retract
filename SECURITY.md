# Security policy

Retract analyzes code it did not write and runs an LLM agent over the results. This
page states what is trusted, what is not, and what the agent is not allowed to do.

## Supported versions

`0.1.x` receives security fixes. Older versions are unsupported.

## Reporting a vulnerability

Use GitHub's private vulnerability reporting:

<https://github.com/krtk06/retract/security/advisories/new>

Do not open a public issue for a vulnerability. There is no bug bounty. We aim to
acknowledge within 72 hours, triage within 7 days, and coordinate disclosure within
90 days.

## Scope

In scope:

- the web app and its API;
- the eve agent, its tools, and its sandbox;
- repository ingestion and the analysis workers;
- the deployment artifacts in `infra/` and the container images.

## Trust model

Untrusted input:

- repository source, README text, comments, filenames, commit messages;
- dependency metadata and lockfiles;
- output from Semgrep, gitleaks, OSV, coverage, Radon, and the other analyzers;
- anything a model generates.

Trusted:

- application code and the migrations in this repository;
- signed session tokens and the shared agent service token;
- a human approval recorded through the approval queue.

The LLM provider is an external processor. It receives repository snippets and tool
results as part of a request. Do not submit repositories containing live credentials
or data you are not allowed to send to that provider.

## Prompt injection

Repository content is **data, not instructions**. The agent is instructed to ignore
directions embedded in code, comments, READMEs, dependency metadata, and tool output.
That content cannot change the agent's rules, authorize a tool call, or ask it to
reveal secrets.

- The agent has no host shell, no repository shell, and no outbound HTTP tool.
- eve's built-in `bash` runs in an isolated JustBash sandbox with an empty working
  environment; it is not a path to the analyzed repository or the host.
- The agent cannot execute repository code.
- Tool output is data; it cannot authorize another tool call. Consequential tools use
  eve's approval gate.
- High-severity claims require a human approval before they count.
- A prompt injection can still mislead a reader or waste tokens. These are
  mitigations, not proof of immunity.

## Sandbox boundaries

- Analysis runs in the Celery worker, unprivileged, inside the container.
- The worker clones the repository into its data volume and parses untrusted files
  with Semgrep, gitleaks, OSV, and the tree-sitter indexers. A parser compromise is a
  residual risk.
- `read_source` resolves paths against the analyzed snapshot and rejects escapes
  outside it.
- The agent calls the API; it does not connect to Postgres or Redis directly.

## Secrets

- gitleaks scans the snapshot for committed secrets.
- The agent can read snippets and send them to the configured LLM provider. Secret
  redaction before provider calls is a planned control; until it exists, do not submit
  repositories containing live secrets.
- The agent has no outbound HTTP tool, so it cannot exfiltrate a secret to an
  arbitrary endpoint. It can still include a snippet in a model request.

## What the agent is not allowed to do

- Run arbitrary code on the host or in the repository.
- Read another account's repository. API ownership checks and the acting-user header
  scope every tool call.
- Publish a score.
- Approve or dismiss a finding without a human decision.
- Start an analysis without the user asking; `run_analysis` is gated by approval.
- Treat tool output or repository text as authorization for a tool call.

## Known limitations

- Prompt injection can still produce a misleading answer; verification and citations
  reduce the impact but do not eliminate it.
- Secrets may reach the LLM provider until redaction lands.
- Analyzer parsers are attack surface.
- The public demo, when one is deployed, is a sandbox for public repositories,
  not for private or sensitive code.
- LLM spend is bounded per session, per account per month, and by the provider budget,
  but the ledger is not a billing-grade real-time meter.

## Dependency and disclosure policy

Dependencies are pinned and audited in CI. The project intends to add Dependabot,
CodeQL, and OpenSSF Scorecard as part of the P1 supply-chain work. Security fixes are
released as patch versions with a changelog entry; coordinated disclosure follows the
timeline above.

## Related documents

- [`docs/operations.md`](docs/operations.md) — limits, budgets, and the deployment
  runbook.
- [`docs/demo.md`](docs/demo.md) — what the public demo does and does not cover.
