import { defineTool } from "eve/tools";
import { z } from "zod";

import { apiPost } from "../lib/api";
import type { AgentFindingsOut } from "../lib/types";
import { actingAs, analysisId } from "../lib/schema";

const findingSchema = z.object({
  claim: z
    .string()
    .min(3)
    .max(300)
    .describe("One sentence stating the problem"),
  evidence: z
    .string()
    .min(3)
    .max(2000)
    .describe("Why you believe it, citing what the tool output showed"),
  file_path: z
    .string()
    .min(1)
    .max(400)
    .describe("Repository-relative path you actually saw in tool output"),
  line_start: z.number().int().min(1).describe("Cited line, 1-based"),
  line_end: z.number().int().min(1).optional().describe("Cited end line, if the claim spans lines"),
  severity: z.enum(["info", "low", "medium", "high", "critical"]),
  confidence: z
    .number()
    .min(0)
    .max(1)
    .describe("How strongly the tools support the claim, not how important it is"),
  category: z
    .string()
    .min(1)
    .max(64)
    .describe(
      'e.g. "secret", "injection", "weak-crypto", "layering", "coupling", "test-plan", "docstring-plan", "code-review"',
    ),
  recommendation: z
    .string()
    .min(3)
    .max(300)
    .optional()
    .describe(
      "One imperative sentence on how to fix it. Omit unless you have a concrete change in mind; the platform has a generic catalog entry for every category already.",
    ),
});

export default defineTool({
  description:
    "Record one or more findings against an analysis using the platform's verdict schema. Every claim needs a real file_path and line_start from earlier tool output; uncited claims are rejected by the server. Stored as unverified hypotheses that the trust layer re-checks, so confidence should be conservative. This does not require approval: recording a claim is cheap and reversible, judging it is not.",
  inputSchema: z.object({
    analysisId,
    agent: z
      .string()
      .regex(/^eve(:[a-z0-9-]+)?$/)
      .describe('Your role, e.g. "eve:security" or "eve" for the main agent'),
    findings: z.array(findingSchema).min(1).max(25),
    triage: z
      .array(
        z.object({
          finding_id: z.number().int().positive(),
          verdict: z.enum(["false-positive", "dismiss"]),
          reasoning: z.string().max(1000),
          confidence: z.number().min(0).max(1).optional(),
        }),
      )
      .max(25)
      .default([])
      .describe("Existing findings you concluded are false positives"),
    summary: z.string().max(4000).default("").describe("One-paragraph summary of this pass"),
  }),
  async execute({ analysisId, agent, findings, triage, summary }, ctx) {
    // A `recommendation` travels with the claim and the server files it as the
    // finding's remediation. It is optional because the platform already has a
    // deterministic catalog entry for every category; supply one only when you can
    // name a change that is specific to the code in front of you.
    const result = await apiPost<AgentFindingsOut>(
      `/api/analyses/${analysisId}/findings`,
      {
        agent,
        findings: findings.map((finding) => ({
          ...finding,
          line_end: finding.line_end ?? finding.line_start,
        })),
        triage,
        summary,
      },
      { actingAs: actingAs(ctx) },
    );
    return {
      inserted: result.inserted,
      dropped: result.dropped,
      dismissed: result.dismissed,
      promoted_by_verification: result.promoted,
      checked_by_verification: result.checked,
      new_overall_score: result.overall,
      published: result.published,
      reasons: result.reasons,
    };
  },
});
