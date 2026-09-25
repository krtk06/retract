import { defineTool } from "eve/tools";
import { z } from "zod";

import { apiGet } from "../lib/api";
import type { SymbolOut } from "../lib/types";
import { actingAs, analysisId, symbolName } from "../lib/schema";

export default defineTool({
  description:
    "Which modules this module imports. Use it to check dependency direction (a domain module importing infrastructure is a real layering violation) and to find a project's entry points.",
  inputSchema: z.object({
    analysisId,
    module: symbolName.describe("Dotted module path, e.g. pkg.client"),
  }),
  async execute({ analysisId, module }, ctx) {
    const imports = await apiGet<SymbolOut[]>(`/api/analyses/${analysisId}/graph/imports`, {
      query: { module },
      actingAs: actingAs(ctx),
    });
    return { module, count: imports.length, imports };
  },
});
