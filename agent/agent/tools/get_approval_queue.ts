import { defineTool } from "eve/tools";
import { z } from "zod";

import { apiGet } from "../lib/api";
import type { QueueOut } from "../lib/types";
import { actingAs, analysisId } from "../lib/schema";

export default defineTool({
  description:
    "The human approval queue for an analysis: high-severity claims a reviewer has not yet judged, plus the approve/dismiss counts. Check this before stating that an analysis is final; unpublished means a human still owns the decision.",
  inputSchema: z.object({ analysisId }),
  async execute({ analysisId }, ctx) {
    const queue = await apiGet<QueueOut>(`/api/analyses/${analysisId}/approvals/queue`, {
      actingAs: actingAs(ctx),
    });
    return {
      published: queue.published,
      pending_count: queue.pending_count,
      approved_count: queue.approved_count,
      dismissed_count: queue.dismissed_count,
      pending: queue.pending.map((finding) => ({
        id: finding.id,
        agent: finding.agent,
        severity: finding.severity,
        title: finding.title,
        file_path: finding.file_path,
        line_start: finding.line_start,
        confidence: finding.confidence,
      })),
    };
  },
});
