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
 *   AI_INTEL_LLM_PROVIDER=gateway \
 *   AI_INTEL_MODEL=anthropic/claude-sonnet-4.5 \
 *   AI_GATEWAY_API_KEY=... \
 *   AI_INTEL_API_URL=http://localhost:8110 \
 *   AI_INTEL_AGENT_TOKEN=... \
 *   npm run eval -- quality
 *
 * `AI_INTEL_EVAL_LIVE=1` is also honoured so a run can be forced from a shell that
 * already exports the provider variables.
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

const ANALYSIS_ID = 42;

const SKIP_REASON =
  'answer-quality evals need a real model. Set AI_INTEL_LLM_PROVIDER, AI_INTEL_MODEL and a provider key, then run: npm run eval -- quality';

function liveModelConfigured(): boolean {
  if (process.env.AI_INTEL_EVAL_LIVE === "1") return true;
  const provider = process.env.AI_INTEL_LLM_PROVIDER ?? "gateway";
  if (provider === "mock") return false;
  // A gateway run still needs a credential, or it fails deep inside the model call.
  return Boolean(process.env.AI_GATEWAY_API_KEY || process.env.AI_INTEL_API_KEY);
}

export default defineEval<typeof config>({
  description: "Live: answers a repository question with cited evidence",
  tags: ["quality", "live"],
  timeoutMs: 180_000,
  async test(t) {
    if (!liveModelConfigured()) t.skip(SKIP_REASON);

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
