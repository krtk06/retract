import { defineEval } from "eve/evals";
import { includes, satisfies } from "eve/evals/expect";

import type config from "../evals.config";
import { postsSince } from "../fixtures/calls";

/** A cited claim is stored and the platform's re-verification result comes back. */
export default defineEval<typeof config>({
  description: "Records a cited finding through the verdict schema",
  tags: ["findings", "citations"],
  async test(t) {
    const mark = t.context.api.mark();
    const turn = await t.send("Look at the cache key helper. [fixture:cited-finding]");

    turn.expectOk();
    t.calledTool("record_finding", {
      input: { analysisId: 42, agent: "eve:security" },
      output: (output) => (output as { inserted?: number } | undefined)?.inserted === 1,
    });
    t.check(turn.message, includes("app/cache_key.py:11"));

    t.check(
      postsSince(t.context.api, mark)
        .filter((post) => post.path === "/api/analyses/42/findings")
        .map((post) => (post.body as { findings?: { file_path?: string }[] }).findings?.[0]?.file_path),
      satisfies<(string | undefined)[]>(
        (paths) => paths.includes("app/cache_key.py"),
        "the stored claim carries its citation",
      ),
    );
  },
});
