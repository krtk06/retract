import { defineAgent } from "eve";
import { mockModel } from "eve/evals";

const mock = process.env.AI_INTEL_LLM_PROVIDER === "mock";

export default defineAgent({
  model: mock
    ? mockModel(({ lastUserMessage }) => `mock test review of: ${lastUserMessage ?? "analysis"}`)
    : (process.env.AI_INTEL_MODEL ?? "anthropic/claude-sonnet-4.5"),
  modelContextWindowTokens: 200_000,
  description:
    "Test specialist. Reviews a repository's test suite: coverage of critical paths, missing regression tests for the code the platform flagged, flaky or vacuous tests, and untested error branches. Delegates here for a testing pass.",
});
