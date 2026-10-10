# Retract

Give it a GitHub repository — get back a **Repository Health Score** with verified,
cited findings across code quality, security, testing, documentation, dependencies,
and architecture.

Deterministic analysis tools run first (Semgrep, gitleaks, OSV, coverage,
complexity). An [eve](https://eve.dev) agent then answers questions and runs deep
reviews over the repository's **symbol graph** and those tool results — no vector
store, no embedding retrieval. A verification layer re-checks every agent claim
before it counts, and high-severity claims wait for a human. See `docs/RESEARCH.md`
for the research basis and `implementation.md` for the build plan.

## Architecture

```text
                    ┌──────────────────────────┐
  browser ────────► │  frontend (Vite + React) │
                    └────┬──────────────┬──────┘
                         │ /api/*       │ /eve/v1/*  (chat, approvals, streams)
                         ▼              ▼
        ┌────────────────────────┐  ┌──────────────────────────────┐
        │  backend (FastAPI)     │  │  agent/ (eve)                │
        │  repos · analyses      │  │  17 tools over graph/findings│
        │  deterministic tools   │◄─┤  5 review subagents         │
        │  verification + trust  │  │  HITL: run_analysis,         │
        └───────┬───────────────┘  │        decide_finding         │
                │                  └──────────────────────────────┘
                ▼
   Postgres (analyses, symbols, edges, findings)   Redis (progress events)
                ▲
                │  Celery worker: ingest → index → 8 analyzers → verify → score
```

The agent holds no state of its own: every fact it reports comes from the API, and
every claim it records is stored as an unverified `hypothesis` that the trust layer
re-checks. The agent cannot publish a score or judge a finding by itself.

## Quickstart (Docker)

```bash
cp .env.example .env      # set RETRACT_AGENT_TOKEN and RETRACT_JWT_SECRET
docker compose --env-file .env -f infra/docker-compose.yml up --build
```

`--env-file .env` is required, not decorative. Compose looks for an implicit `.env`
next to the compose file, and both compose files live in `infra/`, so a `.env` at
the repository root is silently ignored and every required secret comes back
missing. Passing the file explicitly is what makes the root `.env` do double duty
for both local (non-Docker) development and the containers. Passing secrets inline
instead also works.

- Frontend: http://localhost:5173 (Vite dev server)
- API: http://localhost:8000 (`/api/health`, OpenAPI at `/docs`)
- Agent: http://localhost:3000 — its bundled UI is at `/`, and its HTTP API at
  `/eve/v1/*` (the eve React SDK's base path). There is no UI at `/eve`; that path
  belongs to the API prefix only.

### Production

```bash
docker compose --env-file .env -f infra/docker-compose.prod.yml up --build
```

with `POSTGRES_USER`, `POSTGRES_PASSWORD`, `RETRACT_JWT_SECRET` and
`RETRACT_AGENT_TOKEN` in `.env` (see `.env.example`). They are deliberately
required with no defaults: refusing to start beats starting an agent that can
reach the API unauthenticated. Note that *every* compose subcommand interpolates
the file, so `ps` and `down` need those variables too.

The LLM credential is *not* in that list, because the agent validates it itself,
per provider: `openai` reads `RETRACT_API_KEY` and `gateway` reads
`AI_GATEWAY_API_KEY`, and a missing or placeholder one stops the agent at startup
with a message naming the variable — which is why no dummy value is needed for a
provider that never calls the gateway.

Differences from the dev stack, all deliberate:

| | dev | prod |
| --- | --- | --- |
| Frontend | Vite dev server, HMR | nginx serving the built bundle |
| Published ports | 5173, 8000, 3000 | 80 only — the API and agent are internal |
| Healthchecks | none | every service; dependents wait for `service_healthy` |
| Users | default | api and agent are non-root (`intel`, `eve`) with read-only code dirs; **the nginx frontend runs as root master** (it binds :80) |
| Agent state | ephemeral | `agent_state` volume, so sessions survive restarts |
| Secrets | dev defaults | refused at startup if unset |
| Migrations | on boot | on boot, before uvicorn |

The frontend is the one container that is not unprivileged. nginx's master process
needs `CAP_NET_BIND_SERVICE` to bind port 80, so hardening it means moving to 8080
as the `nginx` user and changing the compose port mapping. That has not been done.

GitHub OAuth is required in production (`RETRACT_DEV_LOGIN=0` is forced), and the
session cookie is marked `Secure`, so the frontend must be served over HTTPS —
put a TLS-terminating proxy in front and set `PUBLIC_URL`.

Set `RETRACT_DEV_LOGIN=1` for passwordless dev login, or configure a GitHub OAuth
app (`RETRACT_GITHUB_CLIENT_ID` / `..._SECRET`).

**One account per person.** Sign-in asks GitHub for `read:user user:email`, and a
verified email that already belongs to an account in this app attaches the GitHub
identity to it, so signing in with GitHub and with a password reach the same
repositories and the same history. Without that, each sign-in mints a separate
account with its own empty dashboard. Three rules keep it from handing an account
to the wrong person: only *verified* addresses link; an account already tied to a
different GitHub identity is never claimed; and a password-less account (a
dev-bypass leftover) is never auto-adopted. `user:email` is read-only — your email
address, no repository access.

`RETRACT_FRONTEND_URL` is where GitHub sends the user back to — the value must
match the port the frontend actually serves on, or a successful sign-in lands on
a dead page. It also carries failed sign-ins: the callback redirects a browser
back here with `?auth_error=<code>` rather than answering an HTML navigation with
JSON (`expired_state`, `used_state`, `not_configured`, `exchange_failed`,
`profile_failed`). A sign-in attempt stays valid for 30 minutes — long enough to
find a password manager and a 2FA app.

## Local development

The eve agent needs **Node >= 24** and the backend needs Postgres and Redis. With
those in place, one command starts everything (API, worker, agent, frontend):

```bash
cp .local/env.sh.example .local/env.sh   # machine-specific ports, paths, secrets
source ~/.nvm/nvm.sh && nvm install 24
bash scripts/dev-local.sh start
```

- Frontend: http://localhost:5175 · API: http://localhost:8110 · Agent: http://localhost:3000

Or run the pieces individually:

```bash
cd backend && . .venv/bin/activate && alembic upgrade head
uvicorn app.main:app --port 8000
celery -A app.tasks.celery_app:celery_app worker -l info

cd frontend && npm run dev
cd agent && npm run dev            # eve dev; or `npm run build && npm start`
```

## Benchmark

The pipeline is scored against fixture repositories with known planted conditions:

```bash
cd backend
python -m app.benchmark --analysis-id 1 --stdout           # re-score an existing run
python -m app.benchmark --analysis-id 1 --out ../benchmark/reports/Chaty.md
```

Latest run on `benchmark/seedy-python-app` (analysis #18, 11 planted expectations):

| Metric | Value |
| --- | --- |
| Recall | **100%** (10/10 detectable expectations found) |
| Precision (deduplicated) | **91%** (10 matched, 1 unenumerated, 5 duplicate reports) |
| Precision (raw, per finding) | 62% |
| F1 | 0.77 |
| Verification coverage | 92% (23 verified / 2 hypothesis) |
| Planted false positives triaged | 1/1 dismissed |

The score curve is calibrated against several real repositories, not this fixture. See
[Scoring](#scoring) and [benchmark/REPORT.md](benchmark/REPORT.md).

Two numbers are reported on purpose. A ground-truth file enumerates *conditions*,
while a pipeline reports findings per *(tool × rule × occurrence)*, so flagging one
hardcoded key with three rules is three findings for one problem. `Precision
(deduplicated)` excludes repeat reports of an already-matched condition;
`Precision (raw)` does not. The report lists every duplicate so the noise is
visible rather than averaged away.

### Defect this benchmark surfaced, and the fix

The first run flagged a finding in `app/settings.py:1` under
`category: vulnerability` — the AWS key was filed as a generic vulnerability
rather than a `secret`, putting it in the wrong pillar and the wrong ground-truth
bucket. Cause: `semgrep.py` mapped *every* rule containing `.security.` to
`vulnerability`, and semgrep's credential rules live under `generic.secrets.*`,
which also satisfies that test.

`categorize_check()` now tests the secrets namespace first, covered by
`tests/test_semgrep_categories.py` (10 cases). Re-scored against the same findings
with the corrected category, deduplicated precision goes **91% → 100%** and the
finding is correctly recognised as a repeat report of the same key.

The committed report still shows 91% because analysis #18 predates the fix; the
next run with semgrep installed will show 100%. Semgrep is not installed in this
development environment, so the fix is verified by unit test and by re-scoring,
not by a fresh end-to-end run.

## Scoring

The health score is computed, not vibes:

```
per-pillar score = 100 / (1 + weighted_findings_per_KLOC / 100)
overall          = min(weighted_mean, worst_pillar + 15)
```

Three constants, all exported and covered by tests:

| Constant | Value | Meaning |
| --- | --- | --- |
| `HALF_SCORE_DENSITY` | 30 | weighted finding-points per KLOC at which a pillar scores 50 |
| `COUNT_HALF_SCORE_PENALTY` | 20 | the same half-score point when no LOC was measured, in raw points |
| `WORST_PILLAR_HEADROOM` | 15 | how far the overall may sit above its worst pillar |
| `SEVERITY_WEIGHT` | 30/20/10/5 | critical/high/medium/low |

`HALF_SCORE_DENSITY` has been 250, then 100, and is now **30**. It was 250 until the
pipeline ran on a real repository instead of only an 83-line fixture; it was 100 after
that single run, which turned out to be far too lenient once measured against several
repositories at once — at 100 every repository measured scored 87–92, including one with
four high-severity credential findings. The worst-pillar density across five real
repositories clusters in 22–39 points per KLOC, so 30 puts a typical repository's weakest
dimension near half marks:

| | at 100 | at 30 |
| --- | --- | --- |
| `krtk06/Chaty`, 2 565 LOC, 13 findings | 88 | **64** |
| `psf/requests`, 12 032 LOC, 63 findings | 92 | **72** |
| `pallets/click`, 30 181 LOC, 164 findings | 90 | **62** |
| `pallets/flask`, 18 352 LOC, 163 findings | 87 | **59** |
| `encode/httpx`, 17 753 LOC, 157 findings | 87 | **59** |

Per-repository reports and the full sweep are in
[benchmark/REPORT.md](benchmark/REPORT.md).

**When no LOC was measured**, density cannot be computed at all — the indexer stores
`loc = 0` for a repository it cannot index. The curve then switches to raw weighted
finding-points (`COUNT_HALF_SCORE_PENALTY`) instead of dividing by a tiny floor, and the
payload reports `basis: "count"` so the number is never silently compared against a
density-scored one. `octocat/Hello-World` scores 65 this way; under the old floor the
same two trivial findings scored it 15.

Changing either constant changes every score without changing the formula version,
so the dashboard withholds the run-over-run delta when the calibration differs, not
just when the version does. `python -m app.benchmark` prints a sensitivity table
over both constants for any analysis, which is how the value above was chosen —
from two repositories and the trade-off between them, not from one anecdote.

**Known limitation:** a pillar nobody measured scores 100 and flatters the mean.
`psf/requests` has zero dependency findings and scores 100 there. Unmeasured is not
the same as clean, and the current aggregation does not distinguish them.

## Fix with your agent

Every open finding has a **Fix with your agent** button. It copies a complete
fix brief — the instruction, the finding's identity and citation, the cited
code, and the detector's evidence — plus the install command, ready to paste
into your own coding agent:

```
npx skills add krtk06/retract --skill retract
```

The skill (`skills/retract/` in this repository) teaches the agent the part it
cannot guess: what Retract's verification actually re-checks, which fixes
survive re-analysis per category, and how the score moves. The loop:

1. Click the button on a finding, paste into opencode / Claude Code / Codex.
2. The skill fixes the code, adds a regression test, and runs the repo's own
   checks — it stops before committing.
3. You push, then click **Re-analyze** on the repository: the pipeline
   re-clones at the new HEAD and re-scores.
4. Compare runs on the analysis page (History → A/B) to see the delta.

Two honest notes. The overall is capped at `worst_pillar + 15`, so while the
cap binds only fixing the worst pillar moves the headline — a fix elsewhere
still raises its pillar. And dismissed findings have the button disabled:
Retract already decided they are false positives, and "fixing" one would be
wrong.

Because the skill quotes the scoring constants, `scripts/verify-skill.sh`
runs in CI and fails when `references/scoring.md` drifts from
`backend/app/analysis_engine/scoring.py` — the curve has been retuned twice,
and a stale skill would tell agents to optimise against a dead formula.

## Configuration

| Variable | Where | Purpose |
| --- | --- | --- |
| `RETRACT_DATABASE_URL`, `RETRACT_REDIS_URL` | backend | storage and progress bus |
| `RETRACT_JWT_SECRET` | backend **and** agent | signs session cookies; the agent verifies the exchanged eve token (`iss=ai-intel`, `aud=eve-agent`) |
| `RETRACT_AGENT_TOKEN` | backend **and** agent | shared secret the agent presents on service calls (`X-Agent-Token`); blank disables agent API access |
| `RETRACT_LLM_PROVIDER` | agent | `mock` for the deterministic fixture model (evals, CI, offline review), `openai`, or `gateway` (the default) |
| `RETRACT_MODEL` | agent | model id (defaults: `gpt-5` for `openai`, `anthropic/claude-sonnet-4.5` for `gateway`); required when `RETRACT_LLM_BASE_URL` is set |
| `RETRACT_LLM_BASE_URL` | agent | optional OpenAI-compatible endpoint (opencode-go, local vLLM, Ollama); no extra dependency |
| `RETRACT_LLM_API_MODE` | agent | `chat` (default, `/chat/completions`) or `responses`; must match the endpoint |
| `RETRACT_LLM_HEADERS` | agent | optional JSON object of extra HTTP headers for a custom endpoint; opencode-go requires `x-opencode-session` or it rejects every request. Single-quote it in `.env` |
| `RETRACT_LLM_API_KEY` | agent | credential for a custom `RETRACT_LLM_BASE_URL` (preferred over `RETRACT_API_KEY`) |
| `RETRACT_API_KEY` | agent | credential for `RETRACT_LLM_PROVIDER=openai` (falls back to `OPENAI_API_KEY`) |
| `AI_GATEWAY_API_KEY` | agent | credential for `RETRACT_LLM_PROVIDER=gateway`; optional otherwise — the agent refuses to start without the credential its chosen provider reads |
| `RETRACT_API_URL` | agent | base URL of the backend API (default `http://localhost:8110`) |

## Checks

```bash
# backend
cd backend && ruff check . && ruff format --check . && mypy && python -m pytest

# frontend
cd frontend && npm run lint && npm run typecheck && npm test && npm run build

# agent
cd agent && npm run typecheck && npm run build && npm run eval
```

`npm run eval` runs the agent's evals hermetically: a fixture model plus an
in-process fixture API, so no provider credentials, database, or containers are
needed. 10 cases / 33 gates cover tool discipline, the citation rule, remediation
recording, multi-turn behaviour, and the human-in-the-loop gates.

Two further cases grade *answer quality* with a judge model. They skip themselves
unless a provider is configured, so CI stays green while the suite stays ready:

```bash
# via OpenAI
RETRACT_LLM_PROVIDER=openai RETRACT_API_KEY=... npm run eval:live -- quality

# via opencode-go (any OpenAI-compatible endpoint)
RETRACT_LLM_PROVIDER=openai \
RETRACT_LLM_BASE_URL=https://opencode.ai/zen/go/v1 \
RETRACT_LLM_API_MODE=chat \
RETRACT_LLM_API_KEY=... \
RETRACT_MODEL=longcat-2.5-preview-free \
npm run eval:live -- quality

# or via the Vercel AI Gateway
RETRACT_LLM_PROVIDER=gateway \
RETRACT_MODEL=anthropic/claude-sonnet-4.5 \
AI_GATEWAY_API_KEY=... \
RETRACT_EVAL_LIVE=1 \
npm run eval:live -- quality
```

Use `eval:live`, not `eval`. `eval` pins `RETRACT_LLM_PROVIDER=mock` as an inline
assignment, which overrides whatever the shell exported — so the same command with
`eval` would silently grade the fixture model. Setting `RETRACT_EVAL_LIVE=1`
alongside a mocked agent is refused outright rather than skipped, because a judge
grading a scripted transcript passes for the wrong reason.

Set `RETRACT_JUDGE_MODEL` if the judge should use the same provider as the agent.

## Layout

- `agent/` — eve agent: instructions, tools, subagents, evals (Node 24)
- `backend/` — FastAPI API, Celery analysis pipeline, Alembic migrations
- `frontend/` — React + Vite dashboard
- `infra/` — Docker Compose services
- `benchmark/` — evaluation repos + ground truth
- `docs/` — research notes, architecture decisions, per-phase review logs
