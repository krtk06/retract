import { defineEvalConfig } from "eve/evals";

import { EXPECTED_AGENT_TOKEN, startFixtureApi, type FixtureApi } from "./fixtures/api-server";

export type EvalContext = {
  api: FixtureApi;
};

/**
 * The agent's tools call the real API, so evals get a deterministic stand-in
 * instead of a database. The fixture validates the service token and the D2
 * citation rule the same way the backend does, so an eval that passes here
 * exercises the real contract.
 */
export default defineEvalConfig<EvalContext>({
  // One at a time: evals share a single fixture API process, so concurrent runs
  // interleave in its request log. Each eval asserts on its own delta, which is
  // only meaningful when nothing else is writing. The suite is ~3s serialized.
  maxConcurrency: 1,
  timeoutMs: 60_000,
  async setup() {
    const api = await startFixtureApi();
    process.env.AI_INTEL_API_URL = api.url;
    process.env.AI_INTEL_AGENT_TOKEN = EXPECTED_AGENT_TOKEN;
    return { api };
  },
  async teardown(context) {
    await context?.api.close();
  },
});
