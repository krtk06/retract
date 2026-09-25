import { defineTool } from "eve/tools";
import { z } from "zod";

import { apiGet } from "../lib/api";
import type { NeighborhoodOut } from "../lib/types";
import { actingAs, analysisId, symbolName } from "../lib/schema";

export default defineTool({
  description:
    "The symbol neighbourhood around one symbol out to a given depth: the nodes and edges within N hops. Use it to understand a module's local structure in one call instead of many caller/callee lookups.",
  inputSchema: z.object({
    analysisId,
    symbol: symbolName,
    depth: z.number().int().min(1).max(3).default(1),
  }),
  async execute({ analysisId, symbol, depth }, ctx) {
    const result = await apiGet<NeighborhoodOut>(
      `/api/analyses/${analysisId}/graph/neighborhood`,
      { query: { symbol, depth }, actingAs: actingAs(ctx) },
    );
    return {
      root: result.root,
      node_count: result.nodes.length,
      nodes: result.nodes,
      edges: result.edges,
    };
  },
});
