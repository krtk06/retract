/**
 * Canned AI Engineering Intelligence API for evals.
 *
 * The evals test the agent's wiring — which tools it reaches for, whether it
 * cites, whether HITL gates hold — not the backend, which has its own pytest
 * suite. So they run against this deterministic stub instead of Postgres.
 *
 * It mirrors the parts of the real contract the agent depends on: the auth
 * service token, the D2 verdict rule (uncited claims are dropped), and the
 * approval endpoint. `RETRACT_API_URL` must point at the printed URL.
 */

import { createServer, type Server } from "node:http";

const ANALYSIS_ID = 42;

const ANALYSIS = {
  id: ANALYSIS_ID,
  repository_id: 7,
  commit_sha: "abc1234",
  status: "done",
  started_at: "2026-09-25T10:00:00Z",
  finished_at: "2026-09-25T10:04:00Z",
  error: null,
  created_at: "2026-09-25T10:00:00Z",
  finding_count: 3,
  loc: 1200,
  score_json: { version: 2, overall: 71 },
  published: true,
  pending_approvals: 0,
  repository: {
    id: 7,
    owner: "acme",
    name: "widgets",
    url: "https://github.com/acme/widgets",
    default_branch: "main",
    created_at: "2026-09-25T09:00:00Z",
    latest_analysis_id: ANALYSIS_ID,
    latest_analysis_status: "done",
  },
};

const GRAPH_SUMMARY = {
  analysis_id: ANALYSIS_ID,
  symbols: { module: 6, function: 11, class: 2 },
  edges: { calls: 14, imports: 9 },
  top_modules: [{ module: "app/api", symbols: 9 }],
};

const SYMBOLS = [
  {
    id: 101,
    name: "authenticate",
    kind: "function",
    file_path: "app/auth.py",
    line_start: 12,
    line_end: 30,
  },
  {
    id: 102,
    name: "build_cache_key",
    kind: "function",
    file_path: "app/cache_key.py",
    line_start: 8,
    line_end: 14,
  },
];

const FINDINGS = [
  {
    id: 900,
    analysis_id: ANALYSIS_ID,
    agent: "gitleaks",
    category: "secret",
    severity: "high",
    title: "Hardcoded SHA1 salt in cache key helper",
    description: "app/cache_key.py:11 assigns a literal salt.",
    file_path: "app/cache_key.py",
    line_start: 11,
    line_end: 11,
    evidence_json: null,
    verifier: "gitleaks",
    confidence: 0.9,
    status: "verified",
    created_at: "2026-09-25T10:02:00Z",
  },
];

const SCORE = {
  version: 2,
  overall: 71,
  loc: 1200,
  kloc: 1.2,
  pillars: {
    security: {
      score: 55,
      findings: 2,
      verified: 1,
      hypotheses: 0,
      dismissed: 0,
      weighted_penalty: 25,
    },
    testing: { score: 80, findings: 1, verified: 1, hypotheses: 0, dismissed: 0, weighted_penalty: 10 },
  },
  previous_overall: 68,
  delta: 3,
};

const TRUST_SUMMARY = {
  analysis_id: ANALYSIS_ID,
  totals: { total: 3, verified: 2, hypothesis: 0, dismissed: 1 },
  verification_coverage: 0.67,
  avg_confidence: 0.72,
  agents: [],
  acceptance_rates: [],
};

const SNIPPET = {
  path: "app/auth.py",
  start_line: 8,
  end_line: 18,
  text: [
    "def authenticate(user, password):",
    '    """Validate credentials."""',
    "    if not user.active:",
    "        return False",
    "    return check_password(user, password)",
  ].join("\n"),
};

export const EXPECTED_AGENT_TOKEN = "eval-agent-service-token";

export type RecordedRequest = {
  method: string;
  path: string;
  query: string;
  agentToken: string | undefined;
  agentUser: string | undefined;
  body: unknown;
};

export type FixtureApi = {
  url: string;
  requests: RecordedRequest[];
  /**
   * Current request-log length. Evals run concurrently against one fixture, so
   * each one marks the log on entry and asserts only on its own delta.
   */
  mark: () => number;
  close: () => Promise<void>;
};

function json(response: import("node:http").ServerResponse, status: number, body: unknown): void {
  const payload = JSON.stringify(body);
  response.writeHead(status, {
    "Content-Type": "application/json",
    "Content-Length": Buffer.byteLength(payload),
  });
  response.end(payload);
}

function recordFindings(body: unknown): { status: number; payload: unknown } {
  const input = (body ?? {}) as {
    agent?: string;
    findings?: { claim?: string; file_path?: string | null }[];
    triage?: unknown[];
  };
  const findings = input.findings ?? [];
  const cited = findings.filter((finding) => Boolean(finding.file_path));
  const uncited = findings.length - cited.length;
  return {
    status: 200,
    payload: {
      analysis_id: ANALYSIS_ID,
      agent: input.agent ?? "eve",
      inserted: cited.length,
      dropped: uncited,
      dismissed: input.triage?.length ?? 0,
      promoted: 0,
      checked: cited.length,
      overall: 68,
      published: true,
      reasons: uncited > 0 ? [`${uncited} uncited claim(s) dropped`] : [],
    },
  };
}

function recordRemediation(body: unknown): { status: number; payload: unknown } {
  const input = (body ?? {}) as {
    agent?: string;
    remediations?: { finding_id?: number; action?: string }[];
  };
  const submitted = input.remediations ?? [];
  const known = new Set(FINDINGS.map((finding) => finding.id));
  const reasons: string[] = [];
  let recorded = 0;
  for (const item of submitted) {
    if (item.finding_id == null || !known.has(item.finding_id)) {
      reasons.push(`finding ${item.finding_id} not found in this analysis`);
      continue;
    }
    recorded += 1;
  }
  return {
    status: 200,
    payload: {
      analysis_id: ANALYSIS_ID,
      agent: input.agent ?? "eve",
      recorded,
      rejected: submitted.length - recorded,
      reasons,
    },
  };
}

export async function startFixtureApi(): Promise<FixtureApi> {
  const requests: RecordedRequest[] = [];

  const server: Server = createServer((request, response) => {
    const chunks: Buffer[] = [];
    request.on("data", (chunk: Buffer) => chunks.push(chunk));
    request.on("end", () => {
      const raw = Buffer.concat(chunks).toString("utf8");
      const url = new URL(request.url ?? "/", "http://fixture.local");
      let body: unknown;
      try {
        body = raw ? JSON.parse(raw) : undefined;
      } catch {
        body = raw;
      }
      requests.push({
        method: request.method ?? "GET",
        path: url.pathname,
        query: url.search,
        agentToken: request.headers["x-agent-token"] as string | undefined,
        agentUser: request.headers["x-agent-user"] as string | undefined,
        body,
      });

      if (request.headers["x-agent-token"] !== EXPECTED_AGENT_TOKEN) {
        json(response, 401, { detail: "Invalid agent token" });
        return;
      }

      const path = url.pathname;
      if (path === "/api/repos") {
        json(response, 200, [ANALYSIS.repository]);
        return;
      }
      if (path === "/api/repos/7/analyze") {
        json(response, 201, { ...ANALYSIS, id: ANALYSIS_ID + 1, status: "pending" });
        return;
      }
      if (path === `/api/analyses/${ANALYSIS_ID}`) {
        json(response, 200, ANALYSIS);
        return;
      }
      if (path === `/api/analyses/${ANALYSIS_ID}/graph/summary`) {
        json(response, 200, GRAPH_SUMMARY);
        return;
      }
      if (path === `/api/analyses/${ANALYSIS_ID}/graph/symbols`) {
        const query = url.searchParams.get("q") ?? "";
        const kind = url.searchParams.get("kind");
        const symbols = SYMBOLS.filter(
          (symbol) =>
            symbol.name.includes(query) && (kind === null || symbol.kind === kind),
        );
        json(response, 200, symbols);
        return;
      }
      if (path === `/api/analyses/${ANALYSIS_ID}/graph/callers`) {
        json(response, 200, [
          { symbol: SYMBOLS[0], callsite_line: 44 },
        ]);
        return;
      }
      if (path === `/api/analyses/${ANALYSIS_ID}/graph/callees`) {
        json(response, 200, SYMBOLS);
        return;
      }
      if (path === `/api/analyses/${ANALYSIS_ID}/graph/imports`) {
        json(response, 200, [SYMBOLS[1]]);
        return;
      }
      if (path === `/api/analyses/${ANALYSIS_ID}/graph/dependents`) {
        json(response, 200, [SYMBOLS[0]]);
        return;
      }
      if (path === `/api/analyses/${ANALYSIS_ID}/graph/path`) {
        json(response, 200, SYMBOLS);
        return;
      }
      if (path === `/api/analyses/${ANALYSIS_ID}/graph/neighborhood`) {
        json(response, 200, { root: SYMBOLS[0], nodes: SYMBOLS, edges: [{ from: 101, to: 102, kind: "calls" }] });
        return;
      }
      if (path === `/api/analyses/${ANALYSIS_ID}/findings`) {
        if (request.method === "POST") {
          const result = recordFindings(body);
          json(response, result.status, result.payload);
          return;
        }
        json(response, 200, FINDINGS);
        return;
      }
      if (path === `/api/analyses/${ANALYSIS_ID}/remediation`) {
        // Without this route record_remediation's eval 404s, and a 404 reads to the
        // model as "this tool does not work" rather than "the fixture is incomplete".
        if (request.method === "POST") {
          const result = recordRemediation(body);
          json(response, result.status, result.payload);
          return;
        }
        json(response, 200, {
          analysis_id: ANALYSIS_ID,
          loc: 2565,
          current_overall: 68,
          projected_overall: 100,
          recoverable_points: 32,
          findings_considered: FINDINGS.length,
          unverified_items: 0,
          truncated_findings: 0,
          work_items: [
            {
              key: "secret",
              pillar: "security",
              action: "Rotate the exposed credential",
              severity: "high",
              effort: "low",
              source: "catalog",
              steps: ["Revoke and reissue at the provider."],
              verify: "Re-run the analysis.",
              references: [],
              findings: FINDINGS.map((finding) => ({
                finding_id: finding.id,
                title: finding.title,
                severity: finding.severity,
                status: finding.status,
                file_path: finding.file_path,
                line_start: finding.line_start,
              })),
              finding_count: FINDINGS.length,
              marginal_points: 32,
              weighted_penalty_removed: 20,
              payoff: 20,
            },
          ],
        });
        return;
      }
      if (path === `/api/analyses/${ANALYSIS_ID}/score`) {
        json(response, 200, SCORE);
        return;
      }
      if (path === `/api/analyses/${ANALYSIS_ID}/trust-summary`) {
        json(response, 200, TRUST_SUMMARY);
        return;
      }
      if (path === `/api/analyses/${ANALYSIS_ID}/snippet`) {
        json(response, 200, SNIPPET);
        return;
      }
      if (path === `/api/analyses/${ANALYSIS_ID}/approvals/queue`) {
        json(response, 200, {
          analysis_id: ANALYSIS_ID,
          published: true,
          pending_count: 0,
          approved_count: 1,
          dismissed_count: 0,
          pending: [],
        });
        return;
      }
      if (path === `/api/analyses/${ANALYSIS_ID}/approvals`) {
        const payload = (body ?? {}) as { finding_id?: number; decision?: string };
        json(response, 200, {
          finding_id: payload.finding_id ?? 0,
          decision: payload.decision ?? "approve",
          finding_status: payload.decision === "dismiss" ? "dismissed" : "verified",
          confidence: 0.9,
          note: null,
          pending_count: 0,
          published: true,
        });
        return;
      }
      json(response, 404, { detail: `no fixture route for ${path}` });
    });
  });

  await new Promise<void>((resolve) => server.listen(0, "127.0.0.1", resolve));
  const address = server.address();
  if (address === null || typeof address === "string") {
    throw new Error("fixture API did not bind a port");
  }

  return {
    url: `http://127.0.0.1:${address.port}`,
    requests,
    mark: () => requests.length,
    close: () =>
      new Promise<void>((resolve, reject) => {
        server.close((error) => (error ? reject(error) : resolve()));
      }),
  };
}
