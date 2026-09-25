import { defineTool } from "eve/tools";
import { z } from "zod";

import { apiGet } from "../lib/api";
import type { SymbolOut } from "../lib/types";
import { actingAs, analysisId, symbolName } from "../lib/schema";

export default defineTool({
  description:
    "What this symbol calls. Use it to trace how input reaches a sink, or to check whether a supposedly-safe helper really validates before using a dangerous operation.",
  inputSchema: z.object({ analysisId, symbol: symbolName }),
  async execute({ analysisId, symbol }, ctx) {
    const callees = await apiGet<SymbolOut[]>(`/api/analyses/${analysisId}/graph/callees`, {
      query: { symbol },
      actingAs: actingAs(ctx),
    });
    return { symbol, count: callees.length, callees };
  },
});
