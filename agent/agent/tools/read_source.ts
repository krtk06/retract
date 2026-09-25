import { defineTool } from "eve/tools";
import { z } from "zod";

import { apiGet } from "../lib/api";
import { actingAs, analysisId } from "../lib/schema";

type SnippetOut = {
  path: string;
  start_line: number;
  end_line: number;
  text: string;
};

export default defineTool({
  description:
    "Read the exact source lines from the analyzed snapshot, around a line you already have from the graph or a finding. This is how you quote code accurately: cite first, claim second. Never cite a line you have not read here or in a tool result.",
  inputSchema: z.object({
    analysisId,
    path: z.string().min(1).max(400).describe("Repository-relative file path, e.g. app/cache_key.py"),
    lineStart: z.number().int().min(1).describe("1-based line to center the snippet on"),
    context: z.number().int().min(0).max(20).default(6).describe("Lines of context each side"),
  }),
  async execute({ analysisId, path, lineStart, context }, ctx) {
    const snippet = await apiGet<SnippetOut>(`/api/analyses/${analysisId}/snippet`, {
      query: { path, line_start: lineStart, context },
      actingAs: actingAs(ctx),
    });
    return snippet;
  },
});
