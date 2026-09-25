import { defineEval } from "eve/evals";
import { satisfies } from "eve/evals/expect";

import type config from "../evals.config";
import { callsSince } from "../fixtures/calls";

/**
 * RAG is gone. If any tool or instruction ever routes the agent back to a
 * vector-search endpoint, this fails.
 */
export default defineEval<typeof config>({
  description: "Never calls a retrieval endpoint",
  tags: ["no-rag"],
  async test(t) {
    const mark = t.context.api.mark();
    await t.send("Search the codebase for anything about passwords. [fixture:graph-drilldown]");

    t.succeeded();
    t.check(
      callsSince(t.context.api, mark),
      satisfies<string[]>(
        (calls) => !calls.some((call) => call.includes("/search")),
        "no request hit a /search endpoint",
      ),
    );
    t.notCalledTool("web_search");
  },
});
