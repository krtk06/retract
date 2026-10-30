# Recording the Retract demo

A public deployment is optional. The fastest way to show the project is a 2–3
minute recording of the local stack, plus five or six screenshots. It avoids DNS,
OAuth, TLS, a cloud firewall, and a production LLM budget.

## What the demo should prove

Show the product, not the infrastructure:

1. A repository becomes a score with a per-pillar breakdown.
2. Every finding cites a file and line and carries a verification state.
3. The fix plan is concrete, not generic advice.
4. The agent answers from the repository graph and the analysis, with citations.

## Pre-flight

- Docker is running, and the repository is at `retract-polish` or later.
- `.env` has:
  - `RETRACT_AGENT_TOKEN` and `RETRACT_JWT_SECRET`
  - `RETRACT_DEV_LOGIN=1`
  - the LLM provider, model, base URL, and key for the agent
- Use a clean browser profile so the recording has no bookmarks, extensions, or
  personal tabs.
- Do not show `.env`, terminal history, API keys, email, or tokens.

## Start the stack

```bash
docker compose --env-file .env -f infra/docker-compose.yml up --build
```

Open http://localhost:5173 and click **Dev login**. If 5173 or 8000 is already
taken, override the host ports:

```bash
RETRACT_FRONTEND_PORT=5176 RETRACT_API_PORT=8010 \
  docker compose --env-file .env -f infra/docker-compose.yml up --build
```

Then open http://localhost:5176.

If the agent answers with a credential error, the provider key is missing or
wrong. The deterministic analysis works without it; the chat does not.

## Seed the analysis before recording

Analysis can take several minutes, which makes a real-time recording drag. Run it
once before recording:

1. Add `https://github.com/urllib3/urllib3` (or a repository you know).
2. Start the analysis.
3. Wait for it to finish.

Then record the completed result and, if you want the progress view, start a
second analysis and cut the wait in editing.

## Storyboard (about 2:30)

| Time | Show | Say |
| --- | --- | --- |
| 0:00–0:15 | Dashboard with the analyzed repository | "Retract gives a GitHub repository a health score with cited findings." |
| 0:15–0:30 | Add-repository form | "It clones the repository and runs deterministic tools first: Semgrep, gitleaks, OSV, coverage, complexity." |
| 0:30–0:50 | Score and pillar breakdown | "The score is composed from six pillars; unmeasured pillars are labelled rather than treated as clean." |
| 0:50–1:15 | Findings table | "Each finding has a severity, a category, and the file and line it came from." |
| 1:15–1:40 | One finding detail | "Claims are verified against the source before they count; high-severity claims wait for a human." |
| 1:40–2:00 | Fixes tab | "The remediation plan is ordered and concrete." |
| 2:00–2:25 | Agent chat | "The agent answers from the symbol graph and the tool results, with citations." |
| 2:25–2:30 | Repository list | Close on the result. |

Keep the mouse movement deliberate. Do not scroll through a wall of findings; pick
one and explain it.

## Screenshots

Save these under `docs/demo/`:

| File | View |
| --- | --- |
| `01-dashboard.png` | Repository list or dashboard with analyzed repos |
| `02-repositories.png` | Add-repository form |
| `03-overview.png` | Score and pillar breakdown |
| `04-findings.png` | Findings table with severities |
| `05-finding.png` | One finding with its source excerpt |
| `06-fixes.png` | Remediation plan |
| `07-agent.png` | Agent answer with citations |

The first six are reproducible:

```bash
scripts/capture-demo.sh http://localhost:5176 docs/demo 133
```

The third argument pins a specific analysis so the storyboard stays on one
repository; omit it to use the newest completed analysis. Log in with **Dev login**
first — the script reuses the browser session. Capture the agent tab manually after
asking a question, because the answer streams and can take a minute.

Use a 1440×900 or 1920×1080 window. The screenshots should be readable at GitHub's
content width; crop browser chrome if it adds nothing.

## Recording settings

- **OBS Studio** or **SimpleScreenRecorder**.
- Canvas: 1920×1080, 30 fps, H.264/MP4.
- Record the browser window, not the whole desktop.
- Hide bookmarks and the downloads bar.
- Use a clean profile with no extensions.
- Record system audio only if you are narrating; otherwise add captions in editing.

## Publishing

- Commit the screenshots and a poster frame.
- Host the video on YouTube (unlisted), Loom, or another video host and link it from
  the README. Do not commit a large MP4 to Git.
- A short GIF can go in the README, but keep it under a few megabytes.

Suggested README block:

```markdown
## Demo

[Watch the 2-minute walkthrough](https://example.com/retract-demo)

![Retract score and findings](docs/demo/03-overview.png)
```

## If the local demo does not start

- **Port 5173/8000/3000 already in use:** stop the old stack with
  `docker compose --env-file .env -f infra/docker-compose.yml down`, or set
  `RETRACT_FRONTEND_PORT`, `RETRACT_API_PORT`, and `RETRACT_AGENT_PORT` to free
  ports. The frontend and API values must match the URL you open.
- **No Dev login button:** the frontend is running a production bundle, not the Vite
  dev server, or `RETRACT_DEV_LOGIN=0`. Use the dev compose file and set the flag.
- **Agent says the credential is missing:** set `RETRACT_LLM_PROVIDER` and its key
  in `.env`, then rebuild the agent — eve compiles the provider and model into the
  image.
- **Signed in but every request returns 401:** the browser is on `127.0.0.1` while
  the cookie was issued for `localhost` (or the reverse). Use one hostname
  consistently and open the URL printed by the dev server.
- **Analysis never finishes:** check the worker and beat logs:
  `docker compose --env-file .env -f infra/docker-compose.yml logs -f retract-worker retract-beat`.

## If you later need a public URL

A live deployment is a separate concern. Use one small VPS (Hetzner or
DigitalOcean), or a managed platform, and follow the production guide. Do not block
the demo on a free-tier capacity lottery.
