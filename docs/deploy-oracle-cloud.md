# Deploying to Oracle Cloud (Always Free)

A complete, copy-pasteable path from a fresh Oracle Cloud account to a Retract
instance on a real HTTPS hostname. It uses only Always Free resources and no paid
domain: a **DuckDNS** name for DNS and **Caddy** for automatic TLS.

Read the whole thing once before starting. Steps 1–2 (network and host firewall) are
where a working deployment most often fails, and neither failure names its cause.

## What you will have at the end

- `https://<your-name>.duckdns.org` serving the app over TLS
- the API and agent reachable only from inside the machine
- Postgres and Redis not published at all
- GitHub sign-in working against the real hostname

## Before you start

- An Oracle Cloud account (the Always Free tier is enough).
- Your GitHub OAuth app (the "Retract" one) — you will update its callback URL.
- The opencode-go API key already in your local `.env`.

---

## 1. Network: open 80 and 443 in Oracle

Oracle blocks inbound traffic by default **in two independent places**. Both must be
opened; opening one and not the other is the most common "it works locally but not
on the internet" failure.

In the OCI console, for your VCN's **public subnet**, add ingress rules to the
**Security List** (or the Network Security Group attached to the instance):

| Source | Protocol | Destination port |
| --- | --- | --- |
| `0.0.0.0/0` | TCP | `80` |
| `0.0.0.0/0` | TCP | `443` |
| your IP (`x.x.x.x/32`) | TCP | `22` |

Keep SSH restricted to your own address rather than `0.0.0.0/0`.

## 2. Network: open 80 and 443 *on the host* too

Oracle's Ubuntu images ship with `iptables` rules that accept SSH and drop the rest,
independently of the Security List. Left alone, your Security List says "allowed" and
the packets still never reach Caddy.

```bash
sudo iptables -I INPUT 6 -m state --state NEW -p tcp --dport 80 -j ACCEPT
sudo iptables -I INPUT 6 -m state --state NEW -p tcp --dport 443 -j ACCEPT
sudo netfilter-persistent save          # survives reboot
sudo iptables -L INPUT --line-numbers   # verify both ACCEPT lines are above the REJECT
```

The rules must sit **above** the final `REJECT`. Inserting at position 6 does that on
the stock image; check, and move them up if not.

## 3. Create the instance

- **Shape:** `VM.Standard.A1.Flex` (Ampere ARM), **2 OCPU / 12 GB** minimum. The
  analysis tools shell out to semgrep and gitleaks and clone repositories; the AMD
  micro shapes (1 GB) will be swapped out by the OOM killer. 4 OCPU / 24 GB is
  comfortable and still Always Free.
- **Image:** Canonical **Ubuntu 24.04** (aarch64). All the images the stack uses
  (`python`, `node:24-alpine`, `redis`, `pgvector/pgvector:pg16`, `nginx`) publish
  arm64 builds, so no emulation is needed.
- **SSH key:** download it; you will need it.
- After creation, give the instance a **reserved public IP** (VNIC → Edit →
  assign a reserved public IP). An *ephemeral* address changes on stop/start, which
  would silently break DNS and your GitHub callback.

Connect:

```bash
ssh -i /path/to/your-key ubuntu@<reserved-public-ip>
```

## 4. Install Docker

```bash
sudo apt-get update && sudo apt-get install -y docker.io docker-compose-v2 git
sudo usermod -aG docker "$USER"     # log out and back in for this to apply
```

## 5. A free hostname with DuckDNS

1. Sign in at <https://www.duckdns.org> and create a subdomain, e.g. `retract-demo`.
2. Set its IP to your **reserved** public IP.
3. Confirm it resolves before continuing:

```bash
dig +short retract-demo.duckdns.org   # must print your public IP
```

Caddy cannot obtain a certificate until this resolves to the machine, so do not
skip it.

## 6. Caddy for TLS

Caddy gets and renews a Let's Encrypt certificate automatically, and needs ports 80
and 443 to do it.

```bash
sudo apt-get install -y debian-keyring debian-archive-keyring apt-transport-https curl
curl -fsSL https://dl.cloudsmith.io/public/caddy/stable/gpg.key \
  | sudo gpg --dearmor -o /usr/share/keyrings/caddy-stable-archive-keyring.gpg
curl -fsSL https://dl.cloudsmith.io/public/caddy/stable/debian.deb.txt \
  | sudo tee /etc/apt/sources.list.d/caddy-stable.list
sudo apt-get update && sudo apt-get install -y caddy
```

Create `/etc/caddy/Caddyfile` (replace the hostname):

```
retract-demo.duckdns.org {
    reverse_proxy 127.0.0.1:8080
}
```

```bash
sudo systemctl reload caddy
```

The container does not exist yet, so Caddy will return 502 for now. That is expected.

## 7. Configure the app

```bash
git clone https://github.com/krtk06/retract.git
cd retract
cp .env.example .env
```

Now edit `.env` and set **all** of the following. Generate the secrets rather than
inventing them:

```bash
openssl rand -hex 32    # run twice: one for JWT, one for the agent token
```

```dotenv
# --- Core ---
POSTGRES_USER=retract
POSTGRES_PASSWORD=<a long random password>
POSTGRES_DB=ai_intel
RETRACT_JWT_SECRET=<openssl rand -hex 32>
RETRACT_AGENT_TOKEN=<openssl rand -hex 32, a different one>

# --- Public address: this exact https host, no path, no trailing slash ---
PUBLIC_URL=https://retract-demo.duckdns.org

# --- Behind Caddy: keep the app off the network, Caddy owns 80/443 ---
BIND_ADDR=127.0.0.1
HTTP_PORT=8080

# --- GitHub OAuth app ---
RETRACT_GITHUB_CLIENT_ID=<from the OAuth app>
RETRACT_GITHUB_CLIENT_SECRET=<from the OAuth app>
RETRACT_GITHUB_OAUTH_REDIRECT_URI=https://retract-demo.duckdns.org/api/auth/github/callback

# --- Email verification (Gmail app password) ---
# Without this, verification links cannot be sent, so a GitHub sign-in can never
# link to an email account — and the only symptom is that signing in with GitHub
# creates a second account, which reads as a bug rather than a misconfiguration.
# The account needs 2FA enabled, then an "App password" from
# https://myaccount.google.com/apppasswords. Note the `%40` for `@`.
RETRACT_SMTP_URL=smtps://you%40gmail.com:your-app-password@smtp.gmail.com:465
RETRACT_MAIL_FROM=Retract <you@gmail.com>

# --- The model: opencode-go is an OpenAI-compatible endpoint ---
RETRACT_LLM_PROVIDER=openai
RETRACT_LLM_BASE_URL=https://opencode.ai/zen/go/v1
RETRACT_LLM_API_MODE=chat
RETRACT_LLM_API_KEY=<your oc_sk_… key>
RETRACT_MODEL=longcat-2.5-preview-free
# Single-quoted: the file is sourced by bash, and unquoted braces lose their quotes.
RETRACT_LLM_HEADERS='{"x-opencode-session":"retract-prod","user-agent":"retract-agent/0.1.0"}'
```

Notes that matter:

- `PUBLIC_URL` **must** be `https://…`. The session cookie is `Secure` in production,
  so a deployment served over plain HTTP cannot sign anyone in.
- `RETRACT_ENVIRONMENT=production` is set by the compose file itself; leave it.
- Do **not** set `RETRACT_DEV_LOGIN=1`. The backend refuses to start in production
  with it, along with a short/published `RETRACT_JWT_SECRET`, a missing agent token,
  `RETRACT_AUTH_COOKIE_SECURE` off, `RETRACT_CORS_ORIGINS=*`, or
  `RETRACT_ALLOW_LOCAL_REPOS=1`.
- `.env` is gitignored. Keep it that way.

## 8. Point the GitHub OAuth app at the hostname

In your OAuth app's settings (`Settings → Developer settings → OAuth Apps → Retract`):

- **Homepage URL:** `https://retract-demo.duckdns.org`
- **Authorization callback URL:** `https://retract-demo.duckdns.org/api/auth/github/callback`

The callback must match `RETRACT_GITHUB_OAUTH_REDIRECT_URI` **exactly**. You can keep
the old `http://localhost:8110/…` entry as an additional URL for local development
(OAuth apps allow several).

## 9. Bring it up

```bash
docker compose --env-file .env -f infra/docker-compose.prod.yml up -d --build --wait
```

`--wait` blocks until every service reports healthy, and the API runs
`alembic upgrade head` before it starts serving. The first build takes several
minutes; the ARM wheels have to compile.

If it exits non-zero, `docker compose --env-file .env -f infra/docker-compose.prod.yml ps`
and `… logs` show which service is unhealthy. The most likely cause is a variable in
step 7 that was left unset or a callback URL that does not match step 8.

## 10. Verify

```bash
curl -s https://retract-demo.duckdns.org/api/health
# {"status":"ok","db":"ok","redis":"ok"}

curl -s -o /dev/null -w '%{http_code}\n' https://retract-demo.duckdns.org/eve/v1/info
# 401 — the agent is reachable through Caddy and refuses anonymous callers
```

Then in a browser:

1. Open `https://retract-demo.duckdns.org` — it must be the app, not a login loop.
2. **Sign in with GitHub**, and confirm you land back on the dashboard.
3. Add a repository, run an analysis, and open a finding — the dashboard feed,
   findings, and the Fixes tab are the parts that depend on the queue and the clone.
4. Open the **Agent** tab and ask it a question; the answer should call the graph
   tools rather than fail. A reply that mentions "Invalid agent token" means
   `RETRACT_AGENT_TOKEN` differs between the API and the agent in `.env`.

## Operating it

```bash
# logs (follow one service, or all)
docker compose --env-file .env -f infra/docker-compose.prod.yml logs -f retract-api

# back up Postgres (this is the only state that cannot be regenerated)

docker compose --env-file .env -f infra/docker-compose.prod.yml exec -T postgres \
  pg_dump -U retract ai_intel | gzip > ~/retract-$(date +%F).sql.gz

# update
git pull
docker compose --env-file .env -f infra/docker-compose.prod.yml up -d --build --wait

# reclaim disk when the boot volume fills (old images, unused data)
docker system prune -f
```

Put the backup on a cron and copy it off the machine — `/data` (the volume with
repository clones) is regenerable, the database is not.

### Things to watch

- **Disk.** Clones accumulate in the `repo_data` volume. The free boot volume is
  finite; `docker system df` and `du -sh /var/lib/docker/volumes` show where it went.
- **Memory.** An analysis holds a clone plus semgrep's working set. If analyses fail
  with an OOM, the instance is undersized — go to 4 OCPU / 24 GB.
- **The reserved IP.** Keep it reserved. Releasing it changes your address and breaks
  DNS, TLS renewal, and the GitHub callback at once.
