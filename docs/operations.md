# Operating Retract

The deployment guide is [`deploy-oracle-cloud.md`](deploy-oracle-cloud.md). This page
is the day-two runbook: what the limits are, where LLM spend is recorded, and how to
back up, upgrade, and verify the service.

## Limits

All limits are fixed windows in Redis. A Redis outage fails **open** with a warning:
a cache outage must not lock every account out, and the provider budget remains the
hard stop.

| Endpoint | Limit | Charged to |
| --- | --- | --- |
| `POST /api/auth/register` | 10 / hour | client IP |
| `POST /api/auth/login` | 20 / 15 min | client IP |
| `GET /api/auth/github/login` | 20 / 15 min | client IP |
| `GET /api/auth/github/callback` | 20 / 15 min | client IP |
| `GET /api/auth/dev/login` | 5 / hour | client IP |
| `GET /api/auth/verify-email` | 30 / hour | client IP |
| `POST /api/auth/resend-verification` | 5 / hour | user |
| `POST /api/auth/eve-token` | 60 / hour | user |
| `POST /api/repos/{id}/analyze` | 30 / hour | user |

`eve-token` is minted roughly every five minutes by the browser, so its bucket is a
token-mint budget, not a session count.

Development-bypass accounts (`is_dev=True`) additionally get **one repository per
client IP per 24 hours** (`RETRACT_DEV_REPO_PER_IP_TTL_SECONDS`). Re-analyzing the
same repository is allowed. This is a convenience guard, not tenant isolation:
shared NATs share the budget, and it fails open when Redis is unavailable. It is
disabled in production because `RETRACT_DEV_LOGIN=0`.

### The client IP behind Caddy and nginx

The production path is browser → Caddy (`127.0.0.1:8080`) → nginx → API. nginx uses
`real_ip` to recover the browser address from Caddy's `X-Forwarded-For`, then forwards
its own `X-Forwarded-For`. The API trusts forwarded headers only when the direct peer
is in `RETRACT_TRUSTED_PROXY_CIDRS`.

- The Compose network is pinned to `172.28.0.0/16`, so the default
  `RETRACT_TRUSTED_PROXY_CIDRS=172.28.0.0/16` is exact.
- The API and agent are not published; only the frontend binds a host port.
- Never set the trusted list to `*` on a publicly reachable API: any client could
  then choose its own rate-limit bucket with a header.
- A header from an untrusted peer is ignored; the socket address is used instead.

Verify after deployment:

```bash
curl -fsS https://<host>/api/health
scripts/smoke-prod.sh https://<host>
```

`scripts/smoke-prod.sh` checks health, the frontend, TLS, and that `/eve/v1/info`
returns 401 anonymously. It does **not** replace the browser walkthrough in the
deployment guide (GitHub sign-in, add a repository, run an analysis, chat, approve).

## LLM budgets

Budgets are per account per **UTC calendar month**. The month rolls over at
`00:00 UTC` on the first; the previous month's rows stay for audit.

| Account | Monthly budget |
| --- | --- |
| Demo account (`demo`, seeded) | `RETRACT_DEMO_LLM_BUDGET_USD` ($2) |
| Dev-login account | `RETRACT_DEMO_LLM_BUDGET_USD` ($2) |
| GitHub / email account | `RETRACT_USER_LLM_BUDGET_USD` ($10) |
| Whole deployment | `RETRACT_GLOBAL_LLM_BUDGET_USD` ($2 demo-only, $10 standard) |

The agent checks the **lower** of the account's and the deployment's remaining
budget before dispatching a turn, and reports one usage event per completed model
call. A turn already in flight is bounded by eve's per-session caps instead.

**The provider key's own budget is the final hard stop.** Set it to the same amount
as the deployment cap in the provider console. It is the only control that survives
an application bug.

### Which cost source is authoritative

1. **Provider-reported cost**, when the provider returns it. The AI SDK exposes it
   through `step.attempt.metadata`; Retract reads the Vercel AI Gateway's
   `gateway.cost`.
2. **Token prices**, when the provider does not report dollars. opencode-go is this
   case: its OpenAI-compatible response does not surface `list_cost`, so
   `RETRACT_LLM_INPUT_COST_PER_MTOK` and `RETRACT_LLM_OUTPUT_COST_PER_MTOK` are the
   authoritative prices. Re-check them when the provider changes its pricing. They
   were `$0.25/M` input and output for `deepseek-v4.1-flash` when verified.
3. **Token ceiling**, when neither dollars nor prices are available. Set
   `RETRACT_LLM_MONTHLY_TOKEN_BUDGET` (for example `2000000` for demo). Dollars are
   then not measurable, and this ceiling is the fallback.

The audit row is keyed by the model call's idempotency key, so a retried usage report
does not double-charge. The per-account aggregate is updated in the same transaction.

### Per-session caps

These are eve build inputs (`RETRACT_AGENT_MAX_INPUT_TOKENS`,
`RETRACT_AGENT_MAX_OUTPUT_TOKENS`, `RETRACT_AGENT_MAX_COST_USD`) compiled into the
agent image. They stop one runaway conversation; the monthly ledger stops the month.
Changing them requires rebuilding the agent.

For opencode-go the token caps are the ones that fire: eve's dollar cap depends on
provider-reported cost, which this provider does not supply. The API's token-price
ledger still tracks the approximate dollars.

### Changing the model or provider

Provider, model, base URL, API mode, and non-secret headers are **build-time**
inputs because eve compiles the agent definition into the image. Change them in
`.env`, then:

```bash
docker compose --env-file .env -f infra/docker-compose.prod.yml build retract-agent
docker compose --env-file .env -f infra/docker-compose.prod.yml up -d --wait
```

The runtime environment must carry the same values or the compiled manifest and the
live model disagree. The API key is runtime-only: the build uses a non-secret
placeholder, and `scripts/verify-agent-build.sh` fails if that placeholder appears in
the compiled output.

## Backups

Postgres is the only state that cannot be regenerated. Repository clones under
`/data` can be re-cloned, and `.eve` holds in-flight agent sessions.

```bash
docker compose --env-file .env -f infra/docker-compose.prod.yml exec -T postgres \
  pg_dump -U "$POSTGRES_USER" "$POSTGRES_DB" | gzip > ~/retract-$(date +%F).sql.gz
```

Schedule it (for example `0 3 * * *`) and copy the file off the instance. A backup
that has never been restored is a hope, not a backup: restore into a scratch database
occasionally.

## Upgrades

```bash
cd /home/ubuntu/retract
git pull
docker compose --env-file .env -f infra/docker-compose.prod.yml up -d --build --wait
scripts/smoke-prod.sh https://<host>
```

The API runs `alembic upgrade head` before serving. If the deploy fails, inspect:

```bash
docker compose --env-file .env -f infra/docker-compose.prod.yml ps
docker compose --env-file .env -f infra/docker-compose.prod.yml logs --tail=100 retract-api
```

The most common causes are a missing variable in `.env`, a build-time model change
made without rebuilding the agent, and an OAuth callback that does not match
`PUBLIC_URL`.

## Routine checks

- **Disk:** `docker system df`, `du -sh /var/lib/docker/volumes`. Prune old images
  with `docker system prune -f`; repository clones accumulate in `repo_data`.
- **Memory:** an analysis holds a clone plus semgrep's working set. OOM-killed
  analyses mean the instance is undersized.
- **Spend:** compare the provider console's month-to-date total with the deployment
  cap. The API ledger is per account; the provider console is the final authority.
- **Rate limits:** a 429 is expected under abuse. `Retry-After` says when the window
  resets; the API logs a warning if Redis itself is unavailable and the limiter
  failed open.
- **TLS:** Caddy renews automatically. A failed renewal usually means DNS no longer
  points at the reserved IP.
