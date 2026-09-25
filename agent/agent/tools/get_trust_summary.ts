import { defineTool } from "eve/tools";
import { z } from "zod";

import { apiGet } from "../lib/api";
import type { TrustSummaryOut } from "../lib/types";
import { actingAs, analysisId } from "../lib/schema";

export default defineTool({
  description:
    "Trust summary: how much of the analysis was independently verified, average confidence after calibration, per-source acceptance rates, and whether the analysis is published or still awaiting human approval.",
  inputSchema: z.object({ analysisId }),
  async execute({ analysisId }, ctx) {
    const summary = await apiGet<TrustSummaryOut>(`/api/analyses/${analysisId}/trust-summary`, {
      actingAs: actingAs(ctx),
    });
    return summary;
  },
});
