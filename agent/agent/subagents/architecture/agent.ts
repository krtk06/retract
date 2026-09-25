import { defineAgent } from "eve";
import { mockModel } from "eve/evals";

const mock = process.env.AI_INTEL_LLM_PROVIDER === "mock";

export default defineAgent({
  model: mock
    ? mockModel(
        ({ lastUserMessage }) => `mock architecture review of: ${lastUserMessage ?? "analysis"}`,
      )
    : (process.env.AI_INTEL_MODEL ?? "anthropic/claude-sonnet-4.5"),
  modelContextWindowTokens: 200_000,
  description:
    "Architecture specialist. Reviews module structure and dependency direction: layering violations, cycles, god modules, duplicated logic across layers, and misplaced responsibilities. Delegates here for an architecture pass.",
});
