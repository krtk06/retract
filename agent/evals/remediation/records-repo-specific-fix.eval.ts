import { defineEval } from "eve/evals";
import { satisfies } from "eve/evals/expect";

import type config from "../evals.config";
import { callsSince, postsSince } from "../fixtures/calls";

type RemediationBody = {
  agent?: string;
  remediations?: {
    finding_id?: number;
    action?: string;
    steps?: string[];
  }[];
};

/**
 * Attaching a fix spends model tokens and writes to the analysis, so it parks for
 * approval — the same gate `run_analysis` uses. The eval also pins the citation
 * rule, because a fix with no `file:line` is indistinguishable from a guess.
 */
export default defineEval<typeof config>({
  description: "Recording a remediation waits for the reviewer, and cites the code",
  tags: ["hitl", "remediation"],
  async test(t) {
    const mark = t.context.api.mark();
    const session = await t.session();
    await session.send("Attach a repo-specific fix for the cache salt. [fixture:remediation-plan]");

    session.requireInputRequest({ toolName: "record_remediation" });
    t.check(
      callsSince(t.context.api, mark),
      satisfies<string[]>(
        (calls) => !calls.includes("POST /api/analyses/42/remediation"),
        "no fix was written before approval",
      ),
    );

    await session.respondAll("approve");

    const posted = postsSince(t.context.api, mark).filter(
      (post) => post.path === "/api/analyses/42/remediation",
    );
    t.check(
      posted.map((post) => post.body as RemediationBody),
      satisfies<RemediationBody[]>(
        (bodies) =>
          bodies.some((body) =>
            (body.remediations ?? []).some(
              (item) =>
                item.finding_id === 900 &&
                typeof item.action === "string" &&
                item.action.length > 0 &&
                // The fix must point at the same code the finding did, or it is a
                // guess dressed as advice.
                (item.steps ?? []).some((step) => step.includes("app/cache_key.py")),
            ),
          ),
        "the approved fix was recorded against finding 900 and cites its file:line",
      ),
    );
  },
});
