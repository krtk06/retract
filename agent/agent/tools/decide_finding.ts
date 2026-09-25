import { defineTool } from "eve/tools";
import { always } from "eve/tools/approval";
import { z } from "zod";

import { apiPost } from "../lib/api";
import type { ApprovalOut } from "../lib/types";
import { actingAs, analysisId } from "../lib/schema";

export default defineTool({
  description:
    "Record a human reviewer's decision on a pending finding (approve or dismiss). This writes an audit record attributed to a person, so it always requires approval, and it must never be called to approve your own claim. Surface the pending finding to the user and let them decide.",
  inputSchema: z.object({
    analysisId,
    findingId: z.number().int().positive().describe("Finding id from get_approval_queue"),
    decision: z.enum(["approve", "dismiss"]),
    note: z.string().max(1000).optional().describe("Reviewer's reason, stored in the audit trail"),
  }),
  approval: always(),
  async execute({ analysisId, findingId, decision, note }, ctx) {
    const result = await apiPost<ApprovalOut>(
      `/api/analyses/${analysisId}/approvals`,
      { finding_id: findingId, decision, note: note ?? null },
      { actingAs: actingAs(ctx) },
    );
    return {
      finding_id: result.finding_id,
      decision: result.decision,
      finding_status: result.finding_status,
      confidence: result.confidence,
      pending_count: result.pending_count,
      published: result.published,
    };
  },
});
