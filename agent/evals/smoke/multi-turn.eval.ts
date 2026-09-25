import { defineEval } from "eve/evals";
import { equals, satisfies } from "eve/evals/expect";

import type config from "../evals.config";
import { callsSince } from "../fixtures/calls";

/**
 * Two turns in one session, each with its own fixture script.
 *
 * A fixture model keyed on cumulative tool results drifts once a second turn can
 * see the first turn's results, so this pins per-turn behavior: the first marker
 * still reaches for the graph, and the second one is answered from its own script
 * rather than repeating the previous turn's tool call.
 */
export default defineEval<typeof config>({
  description: "Handles two scripted turns in one session",
  tags: ["smoke", "multi-turn"],
  async test(t) {
    const mark = t.context.api.mark();
    const first = await t.send("Status please. [fixture:graph-answer]");
    first.expectOk();

    const second = await first.session.send("And the source? [fixture:graph-drilldown]");
    second.expectOk();

    await t.require(second.sessionId, equals(first.sessionId));

    t.calledTool("get_analysis", { input: { analysisId: 42 }, count: 1 });
    t.calledTool("find_symbols", { input: { analysisId: 42, query: "auth" }, count: 1 });
    t.calledTool("read_source", { input: { analysisId: 42, path: "app/auth.py" }, count: 1 });
    t.check(
      callsSince(t.context.api, mark),
      satisfies<string[]>(
        (calls) =>
          calls.includes("GET /api/analyses/42") &&
          calls.includes("GET /api/analyses/42/snippet"),
        "each turn ran only its own tools",
      ),
    );
  },
});
