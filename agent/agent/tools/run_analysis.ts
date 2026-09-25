import { defineTool } from "eve/tools";
import { always } from "eve/tools/approval";
import { z } from "zod";

import { apiPost } from "../lib/api";
import type { AnalysisOut } from "../lib/types";
import { actingAs } from "../lib/schema";

export default defineTool({
  description:
    "Start a new analysis run for a tracked repository: clones it, indexes symbols, and runs the deterministic analyzers. Expensive and outward-facing (it fetches from the network and writes an analysis), so it always waits for the human to approve. Only call this when the user actually asks for a fresh run.",
  inputSchema: z.object({
    repositoryId: z
      .number()
      .int()
      .positive()
      .describe("Repository id from list_repositories"),
  }),
  approval: always(),
  async execute({ repositoryId }, ctx) {
    const analysis = await apiPost<AnalysisOut>(
      `/api/repos/${repositoryId}/analyze`,
      {},
      { actingAs: actingAs(ctx) },
    );
    return {
      analysis_id: analysis.id,
      status: analysis.status,
      note: "The deterministic pipeline is running. Use get_analysis to poll, then get_score once status is done.",
    };
  },
});
