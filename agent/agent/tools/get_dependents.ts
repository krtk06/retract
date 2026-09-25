import { defineTool } from "eve/tools";
import { z } from "zod";

import { apiGet } from "../lib/api";
import type { SymbolOut } from "../lib/types";
import { actingAs, analysisId, symbolName } from "../lib/schema";

export default defineTool({
  description:
    "Which modules or files depend on this module. Use it to size the impact of a change or to justify a layering violation with a real import edge.",
  inputSchema: z.object({
    analysisId,
    module: symbolName.describe("Dotted module path, e.g. pkg.auth"),
  }),
  async execute({ analysisId, module }, ctx) {
    const dependents = await apiGet<SymbolOut[]>(`/api/analyses/${analysisId}/graph/dependents`, {
      query: { module },
      actingAs: actingAs(ctx),
    });
    return { module, count: dependents.length, dependents };
  },
});
