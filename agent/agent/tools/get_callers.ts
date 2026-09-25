import { defineTool } from "eve/tools";
import { z } from "zod";

import { apiGet } from "../lib/api";
import type { CallerOut } from "../lib/types";
import { actingAs, analysisId, symbolName } from "../lib/schema";

export default defineTool({
  description:
    "Who calls this symbol. Use it to measure blast radius before reporting an issue: a finding on a widely-called function matters more than one on a leaf.",
  inputSchema: z.object({ analysisId, symbol: symbolName }),
  async execute({ analysisId, symbol }, ctx) {
    const callers = await apiGet<CallerOut[]>(`/api/analyses/${analysisId}/graph/callers`, {
      query: { symbol },
      actingAs: actingAs(ctx),
    });
    return {
      symbol,
      count: callers.length,
      callers: callers.map((caller) => ({
        name: caller.symbol.name,
        kind: caller.symbol.kind,
        file_path: caller.symbol.file_path,
        line_start: caller.symbol.line_start,
        callsite_line: caller.callsite_line,
      })),
    };
  },
});
