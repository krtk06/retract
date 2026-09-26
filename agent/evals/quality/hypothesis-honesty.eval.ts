/**
 * Live: does the agent present unverified claims as confirmed?
 *
 * Skips itself unless a real provider is configured — see
 * `./grounded-answers.eval.ts` for how to enable this suite.
 */
import { defineEval } from "eve/evals";

import type config from "../evals.config";

const SKIP_REASON =
  'answer-quality evals need a real model. Set AI_INTEL_LLM_PROVIDER, AI_INTEL_MODEL and a provider key, then run: npm run eval -- quality';

function liveModelConfigured(): boolean {
  if (process.env.AI_INTEL_EVAL_LIVE === "1") return true;
  const provider = process.env.AI_INTEL_LLM_PROVIDER ?? "gateway";
  if (provider === "mock") return false;
  return Boolean(process.env.AI_GATEWAY_API_KEY || process.env.AI_INTEL_API_KEY);
}

export default defineEval<typeof config>({
  description: "Live: distinguishes verified findings from unverified hypotheses",
  tags: ["quality", "live"],
  timeoutMs: 180_000,
  async test(t) {
    if (!liveModelConfigured()) t.skip(SKIP_REASON);

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
