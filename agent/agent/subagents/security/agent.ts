import { defineAgent } from "eve";
import { mockModel } from "eve/evals";

const mock = process.env.RETRACT_LLM_PROVIDER === "mock";

export default defineAgent({
  model: mock
    ? mockModel(({ lastUserMessage }) => `mock security review of: ${lastUserMessage ?? "analysis"}`)
    : (process.env.RETRACT_MODEL ?? "anthropic/claude-sonnet-4.5"),
  modelContextWindowTokens: 200_000,
  description:
    "Security specialist. Reviews a repository for secrets, injection, unsafe crypto, auth and authorization gaps, and dangerous dependency use. Delegates here for a security pass, not for general code review.",
});
