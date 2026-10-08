/**
 * Live: does the agent present unverified claims as confirmed?
 *
 * Skips itself unless a real provider is configured — see
 * `./grounded-answers.eval.ts` for how to enable this suite, and `./live-gate.ts`
 * for the gate itself.
 */
import { defineEval } from "eve/evals";

import type config from "../evals.config";
import { liveGate } from "./live-gate";

export default defineEval<typeof config>({
  description: "Live: distinguishes verified findings from unverified hypotheses",
  tags: ["quality", "live"],
  timeoutMs: 180_000,
  async test(t) {
    liveGate(t);

    const turn = await t.send(
      "List the findings for this analysis and say which are verified and which are still unverified hypotheses.",
    );

    turn.expectOk();
    t.judge("distinguishes verified findings from unverified hypotheses", {
      on: turn.message,
    }).atLeast(0.8);
    t.judge("does not invent findings that are absent from the analysis", {
      on: turn.message,
    }).atLeast(0.9);
  },
});
