import { defineEval } from "eve/evals";
import { satisfies } from "eve/evals/expect";

import type config from "../evals.config";
import { callsSince } from "../fixtures/calls";

/**
 * `run_analysis` is gated on human approval. The turn must park on an input
 * request, and the analysis must not start until the human approves.
 *
 * The parked state is asserted on the turn, not the run: a run-level assertion
 * reads the final state, which is "completed" once approval lands.
 */
export default defineEval<typeof config>({
  description: "Starting an analysis waits for human approval",
  tags: ["hitl"],
  async test(t) {
    const mark = t.context.api.mark();
    const session = await t.session();
    const parked = await session.send("Re-analyze acme/widgets. [fixture:run-analysis]");

    parked.calledTool("run_analysis", { status: "pending" });
    t.check(
      callsSince(t.context.api, mark),
      satisfies<string[]>(
        (calls) => !calls.includes("POST /api/repos/7/analyze"),
        "nothing ran before the human decided",
      ),
    );

    session.requireInputRequest({ toolName: "run_analysis" });
    const approved = await session.respondAll("approve");

    approved.calledTool("run_analysis", { status: "completed" });
    t.check(
      callsSince(t.context.api, mark),
      satisfies<string[]>(
        (calls) => calls.includes("POST /api/repos/7/analyze"),
        "the approved call reached the API",
      ),
    );
  },
});
