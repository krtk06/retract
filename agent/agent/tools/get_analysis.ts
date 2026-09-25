import { defineTool } from "eve/tools";
import { z } from "zod";

import { apiGet } from "../lib/api";
import type { AnalysisOut } from "../lib/types";
import { actingAs } from "../lib/schema";

export default defineTool({
  description:
    "Get one analysis: repository, commit, status, finding count, published flag, and pending approvals. Use this to confirm which snapshot you are reasoning about before citing anything.",
  inputSchema: z.object({ analysisId: z.number().int().positive() }),
  async execute({ analysisId }, ctx) {
    const analysis = await apiGet<AnalysisOut>(`/api/analyses/${analysisId}`, {
      actingAs: actingAs(ctx),
    });
    return {
      id: analysis.id,
      repository: analysis.repository
        ? {
            slug: `${analysis.repository.owner}/${analysis.repository.name}`,
            url: analysis.repository.url,
          }
        : null,
      commit_sha: analysis.commit_sha,
      status: analysis.status,
      loc: analysis.loc,
      finding_count: analysis.finding_count,
      published: analysis.published,
      pending_approvals: analysis.pending_approvals,
      error: analysis.error,
      overall_score: (analysis.score_json as { overall?: number } | null)?.overall ?? null,
    };
  },
});
