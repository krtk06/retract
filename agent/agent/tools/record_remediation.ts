import { defineTool } from "eve/tools";
import { always } from "eve/tools/approval";
import { z } from "zod";

import { apiGet, apiPost } from "../lib/api";
import type { FindingOut, RemediationSubmitOut } from "../lib/types";
import { analysisId, actingAs } from "../lib/schema";

/**
 * Record repo-specific fixes for findings the deterministic catalog covers only
 * generically.
 *
 * Always requires approval. It spends model tokens and writes to the analysis, so
 * it sits behind the human gate for the same reason `run_analysis` does — the cost
 * and the persistence are what need consent, not the judgement itself.
 */
export default defineTool({
  description:
    "Attach a repo-specific fix to existing findings. The platform ships a deterministic remediation catalog, so a finding usually already has advice; use this when the catalog's generic steps miss what is actually wrong here, and read the finding and its cited lines first. Each remediation must name the finding_id it applies to and cite the same file:line. Recorded fixes are shown to the user labelled as agent-authored, and are dropped if the finding is later dismissed.",
  inputSchema: z.object({
    analysisId,
    agent: z
      .string()
      .regex(/^eve(:[a-z0-9-]+)?$/)
      .describe('Your role, e.g. "eve:security"'),
    remediations: z
      .array(
        z.object({
          finding_id: z.number().int().positive().describe("Finding id from get_findings"),
          action: z
            .string()
            .min(3)
            .max(300)
            .describe("One imperative sentence: what to change"),
          steps: z
            .array(z.string().min(3).max(500))
            .max(10)
            .default([])
            .describe("Ordered concrete steps, each citing file:line where relevant"),
          effort: z.enum(["low", "medium", "high"]).default("medium"),
          verify: z
            .string()
            .max(500)
            .default("")
            .describe("How to confirm the fix landed, e.g. what re-run should no longer report it"),
          references: z.array(z.string().max(400)).max(5).default([]),
          reasoning: z
            .string()
            .max(1000)
            .default("")
            .describe("Why the catalog's generic advice is not enough for this finding"),
        }),
      )
      .min(1)
      .max(25),
  }),
  approval: always(),
  async execute({ analysisId, agent, remediations }, ctx) {
    // Re-read each finding before authoring advice about it. The model may have
    // cited a finding id from earlier in the conversation, and the finding could
    // have been dismissed since; recording a fix for a dismissed finding is
    // rejected server-side, but finding out here costs one call instead of a
    // confusing empty result.
    const existing = await apiGet<FindingOut[]>(`/api/analyses/${analysisId}/findings`, {
      query: { limit: 200 },
      actingAs: actingAs(ctx),
    });
    const byId = new Map(existing.map((finding) => [finding.id, finding]));

    const skipped: { finding_id: number; reason: string }[] = [];
    const payload = remediations.flatMap((item) => {
      const finding = byId.get(item.finding_id);
      if (!finding) {
        skipped.push({ finding_id: item.finding_id, reason: "no such finding in this analysis" });
        return [];
      }
      if (finding.status === "dismissed") {
        skipped.push({ finding_id: item.finding_id, reason: "finding is dismissed" });
        return [];
      }
      if (!finding.file_path) {
        skipped.push({
          finding_id: item.finding_id,
          reason: "finding has no citation, so a specific fix cannot be justified",
        });
        return [];
      }
      return [
        {
          finding_id: item.finding_id,
          action: item.action,
          steps: item.steps,
          effort: item.effort,
          verify: item.verify,
          references: item.references,
          reasoning: item.reasoning,
        },
      ];
    });

    if (payload.length === 0) {
      return {
        recorded: 0,
        skipped,
        note: "Nothing was recorded. Every remediation referenced a finding that cannot take one.",
      };
    }

    const result = await apiPost<RemediationSubmitOut>(
      `/api/analyses/${analysisId}/remediation`,
      { agent, remediations: payload },
      { actingAs: actingAs(ctx) },
    );

    return {
      recorded: result.recorded,
      rejected: result.rejected,
      skipped,
      reasons: result.reasons,
      note: "The fix plan on the dashboard now shows these as agent-authored.",
    };
  },
});
