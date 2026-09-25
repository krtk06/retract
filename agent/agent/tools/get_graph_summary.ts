import { defineTool } from "eve/tools";
import { z } from "zod";

import { apiGet } from "../lib/api";
import type { GraphSummaryOut } from "../lib/types";
import { actingAs, analysisId } from "../lib/schema";

export default defineTool({
  description:
    "Graph summary for an analysis: symbol counts by kind, edge counts by kind, and the largest modules. Use this to orient before drilling into specific symbols.",
  inputSchema: z.object({ analysisId }),
  async execute({ analysisId }, ctx) {
    return await apiGet<GraphSummaryOut>(`/api/analyses/${analysisId}/graph/summary`, {
      actingAs: actingAs(ctx),
    });
  },
});
