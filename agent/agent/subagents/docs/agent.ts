import { defineAgent } from "eve";
import { mockModel } from "eve/evals";

const mock = process.env.AI_INTEL_LLM_PROVIDER === "mock";

export default defineAgent({
  model: mock
    ? mockModel(({ lastUserMessage }) => `mock docs review of: ${lastUserMessage ?? "analysis"}`)
    : (process.env.AI_INTEL_MODEL ?? "anthropic/claude-sonnet-4.5"),
  modelContextWindowTokens: 200_000,
  description:
    "Documentation specialist. Reviews docstrings and public API docs against actual behavior: missing or stale docstrings, documented parameters that do not exist, and modules whose purpose is undocumented. Delegates here for a docs pass.",
});
