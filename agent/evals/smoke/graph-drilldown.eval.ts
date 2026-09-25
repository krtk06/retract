import { defineEval } from "eve/evals";
import { includes } from "eve/evals/expect";

import type config from "../evals.config";

/**
 * Structural answers require reading the cited code, not just locating the
 * symbol: the fixture script escalates find_symbols → read_source.
 */
export default defineEval<typeof config>({
  description: "Cites a source line after locating the symbol and reading it",
  tags: ["graph", "citations"],
  async test(t) {
    const turn = await t.send("Where does authentication happen? [fixture:graph-drilldown]");

    turn.expectOk();
    t.calledTool("find_symbols", { input: { analysisId: 42, query: "auth" } });
    t.calledTool("read_source", { input: { analysisId: 42, path: "app/auth.py" } });
    t.check(turn.message, includes("app/auth.py:12"));
  },
});
