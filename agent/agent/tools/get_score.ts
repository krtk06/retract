import { defineTool } from "eve/tools";
import { z } from "zod";

import { apiGet } from "../lib/api";
import type { ScoreOut } from "../lib/types";
import { actingAs, analysisId } from "../lib/schema";

export default defineTool({
  description:
    "The honest score for an analysis: overall, per-pillar scores, and the delta against the previous run. Quote the overall and the pillar that moved; do not restate the weighting.",
  inputSchema: z.object({ analysisId }),
  async execute({ analysisId }, ctx) {
    const score = await apiGet<ScoreOut>(`/api/analyses/${analysisId}/score`, {
      actingAs: actingAs(ctx),
    });
    const pillars = Object.entries(score.pillars).map(([name, data]) => ({
      name,
      score: data.score,
      findings: data.findings,
      verified: data.verified,
      hypotheses: data.hypotheses,
      dismissed: data.dismissed,
    }));
    return {
      version: score.version,
      overall: score.overall,
      previous_overall: score.previous_overall,
      delta: score.delta,
      loc: score.loc,
      kloc: score.kloc,
      pillars,
    };
  },
});
