# Changelog

All notable changes to this project are documented here. The format is
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and this project follows
[Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.1.0] - 2026-11-02

### Added

- Repository health score across six pillars, with verified, cited findings.
- Deterministic analyzers: Semgrep, gitleaks, OSV, coverage, complexity,
  duplication, docs, and architecture.
- Tree-sitter symbol graph and graph tools; no vector store or embedding retrieval.
- eve agent with typed API tools, specialist subagents, and a citation rule.
- Verification layer and a human approval queue for high-severity hypotheses.
- Prioritized fix plans and the `retract` coding-agent skill.
- Benchmark harness with synthetic ground truth and real-repository calibration.
- Product film, captions, and poster published as the `demo-film` release.

### Security

- Production startup guards for secrets, cookies, CORS, and dev login.
- Private repositories per user, with verified-email account linking.
- Agent service authentication and acting-user scoping.
- Agent instructions treat repository content, dependency metadata, and tool output
  as untrusted data rather than instructions.
- Rate limits on registration, login, GitHub OAuth, dev login, verification,
  eve-token minting, and analysis submission.
- Per-account monthly LLM budgets, a deployment-wide ceiling, and per-session caps.
- Trusted-proxy client-IP resolution for the Caddy → nginx → API path.

### Fixed

- The agent image now receives its provider, model, base URL, API mode, and
  non-secret headers as build inputs; the credential stays runtime-only.
- The backend image selects a checksum-verified gitleaks asset for amd64 and arm64.
- The dev Compose stack passes the same agent build inputs as production and
  supports host-port overrides.

### Documentation

- Oracle Cloud + Caddy deployment guide.
- Operations runbook for limits, budgets, backups, and upgrades.
- Local demo guide, screenshots, and the product film.
