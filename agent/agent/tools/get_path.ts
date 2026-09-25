import { defineTool } from "eve/tools";
import { z } from "zod";

import { apiGet } from "../lib/api";
import type { SymbolOut } from "../lib/types";
import { actingAs, analysisId, symbolName } from "../lib/schema";

export default defineTool({
  description:
    "Shortest call/import path between two symbols, as an ordered list. Use it to prove reachability between a source and a sink, or to show two modules are not coupled after all.",
  inputSchema: z.object({
    analysisId,
    from: symbolName.describe("Starting symbol or module"),
    to: symbolName.describe("Target symbol or module"),
  }),
  async execute({ analysisId, from, to }, ctx) {
    const path = await apiGet<SymbolOut[]>(`/api/analyses/${analysisId}/graph/path`, {
      query: { from, to },
      actingAs: actingAs(ctx),
    });
    return {
      found: path.length > 0,
      length: path.length,
      path: path.map((step, index) => ({
        step,
        name: step.name,
        kind: step.kind,
        file_path: step.file_path,
        line_start: step.line_start,
        is_endpoint: index === 0 || index === path.length - 1,
      })),
    };
  },
});
