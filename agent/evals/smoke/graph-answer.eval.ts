import { defineEval } from "eve/evals";
import { includes, satisfies } from "eve/evals/expect";

import type config from "../evals.config";
import { callsSince } from "../fixtures/calls";

/**
 * The agent must reach for the API before answering, not answer from memory.
 * This also pins the tool-name contract: renaming a tool breaks this eval.
 */
export default defineEval<typeof config>({
  description: "Answers an analysis question by reading the analysis first",
  tags: ["graph", "smoke"],
  async test(t) {
    const mark = t.context.api.mark();
    const turn = await t.send("How did analysis 42 go? [fixture:graph-answer]");

    turn.expectOk();
    t.calledTool("get_analysis", { input: { analysisId: 42 }, count: 1 });
    t.check(turn.message, includes("42"));
    t.check(
      callsSince(t.context.api, mark),
      satisfies<string[]>(
        (calls) => calls.includes("GET /api/analyses/42"),
        "the API received a read for analysis 42",
      ),
    );
  },
});
