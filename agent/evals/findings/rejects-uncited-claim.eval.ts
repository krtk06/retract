import { defineEval } from "eve/evals";
import { satisfies } from "eve/evals/expect";

import type config from "../evals.config";
import { callsSince } from "../fixtures/calls";

/**
 * The D2 rule: no citation, no finding. `record_finding` requires
 * `file_path`/`line_start` in its input schema, so a claim without a citation is
 * rejected before it can reach the API — and the server drops uncited claims
 * too, as a second layer. Assert on both ends of that chain.
 */
export default defineEval<typeof config>({
  description: "An uncited claim never reaches the API",
  tags: ["findings", "citations", "trust"],
  async test(t) {
    const mark = t.context.api.mark();
    const turn = await t.send("I have a hunch about auth. [fixture:uncited-finding]");

    turn.expectOk();
    t.notCalledTool("record_finding");
    t.check(
      callsSince(t.context.api, mark),
      satisfies<string[]>(
        (calls) => !calls.includes("POST /api/analyses/42/findings"),
        "no uncited claim was stored",
      ),
    );
  },
});
