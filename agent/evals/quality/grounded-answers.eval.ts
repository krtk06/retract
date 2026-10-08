/**
 * Live answer-quality evals — the seam for when a real model is available.
 *
 * Everything else in this suite runs against the deterministic fixture model and
 * passes in CI with no credentials. These cases are different in kind: they judge
 * whether the agent's *answers* are correct and well-cited, which a scripted model
 * cannot demonstrate. So each one skips itself unless a real provider is
 * configured, keeping `npm run eval` green while making the suite ready.
 *
 * To run them:
 *
 *   npm run eval:live -- quality
 *
 * with a provider and credential exported (`AI_INTEL_LLM_PROVIDER=gateway`,
 * `AI_GATEWAY_API_KEY=...`, optionally `AI_INTEL_MODEL`). Use `eval:live`, not
 * `eval`: `eval` pins the provider to `mock` inline and would override your
 * export. `AI_INTEL_EVAL_LIVE=1` forces the suite to run rather than skip.
 *
 * Requires a real analysis to exist for the target repository, since the judge
 * grades claims against findings the platform actually stored:
 *
 *   cd backend && python -m app.benchmark --repo seedy-python-app   # check the run exists
 */
import { defineEval } from "eve/evals";
import { includes } from "eve/evals/expect";

import type config from "../evals.config";
import { callsSince } from "../fixtures/calls";
import { liveGate } from "./live-gate";

const ANALYSIS_ID = 42;

export default defineEval<typeof config>({
  description: "Live: answers a repository question with cited evidence",
  tags: ["quality", "live"],
  timeoutMs: 180_000,
  async test(t) {
    liveGate(t);

    const mark = t.context.api.mark();
    const turn = await t.send(
      `For analysis ${ANALYSIS_ID}: which security issues did the analyzers confirm, and where are they? Cite file and line for each.`,
    );

    turn.expectOk();
    // Whatever it answers, it must have looked rather than guessed.
    t.check(callsSince(t.context.api, mark), includes("GET")).label(
      "the agent called the API before answering",
    );
    t.judge("cites a repository-relative file and line for every code claim", {
      on: turn.message,
    }).atLeast(0.8);
    t.judge("does not claim to have verified anything it did not check", {
      on: turn.message,
    }).atLeast(0.8);
  },
});
