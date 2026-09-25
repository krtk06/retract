import { defineTool } from "eve/tools";
import { z } from "zod";

import { apiGet } from "../lib/api";
import type { SymbolOut } from "../lib/types";
import { actingAs, analysisId } from "../lib/schema";

export default defineTool({
  description:
    "Find symbols (functions, classes, modules) by name or kind. This is the platform's replacement for semantic search: match structurally, then read the source. Returns file paths and line numbers you can cite.",
  inputSchema: z.object({
    analysisId,
    query: z.string().min(1).max(200).describe('Name fragment to match, e.g. "auth"'),
    kind: z
      .enum(["function", "class", "method", "module"])
      .optional()
      .describe("Restrict to one symbol kind"),
    limit: z.number().int().min(1).max(100).default(25),
  }),
  async execute({ analysisId, query, kind, limit }, ctx) {
    const symbols = await apiGet<SymbolOut[]>(`/api/analyses/${analysisId}/graph/symbols`, {
      query: { q: query, kind, limit },
      actingAs: actingAs(ctx),
    });
    return { count: symbols.length, symbols };
  },
});
