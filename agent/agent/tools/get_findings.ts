import { defineTool } from "eve/tools";
import { z } from "zod";

import { apiGet } from "../lib/api";
import type { FindingOut } from "../lib/types";
import { actingAs, analysisId } from "../lib/schema";

export default defineTool({
  description:
    "Findings the deterministic analyzers already produced (semgrep, gitleaks, dependency advisories, radon, duplication, tests, docs, architecture). Filter by severity, status, or agent. Read these before forming an opinion so you do not re-report what the platform already knows.",
  inputSchema: z.object({
    analysisId,
    severity: z.enum(["info", "low", "medium", "high", "critical"]).optional(),
    status: z
      .enum(["verified", "hypothesis", "dismissed", "rejected"])
      .optional()
      .describe("verified = passed deterministic re-check; hypothesis = unverified claim"),
    agent: z.string().max(64).optional().describe('Analyzer that produced it, e.g. "semgrep"'),
    limit: z.number().int().min(1).max(200).default(50),
  }),
  async execute({ analysisId, severity, status, agent, limit }, ctx) {
    const findings = await apiGet<FindingOut[]>(`/api/analyses/${analysisId}/findings`, {
      query: { severity, status, agent, limit },
      actingAs: actingAs(ctx),
    });
    return {
      count: findings.length,
      findings: findings.map((finding) => ({
        id: finding.id,
        agent: finding.agent,
        category: finding.category,
        severity: finding.severity,
        title: finding.title,
        description: finding.description,
        file_path: finding.file_path,
        line_start: finding.line_start,
        line_end: finding.line_end,
        verifier: finding.verifier,
        confidence: finding.confidence,
        status: finding.status,
      })),
    };
  },
});
