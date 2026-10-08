import { defineAgent } from "eve";
import { mockModel } from "eve/evals";

const mock = process.env.RETRACT_LLM_PROVIDER === "mock";

export default defineAgent({
  model: mock
    ? mockModel(
        ({ lastUserMessage, toolResults }) =>
          toolResults.length === 0
            ? `mock code review of: ${lastUserMessage ?? "analysis"}`
            : `mock triage after ${toolResults.length} tool call(s)`,
      )
    : (process.env.RETRACT_MODEL ?? "anthropic/claude-sonnet-4.5"),
  modelContextWindowTokens: 200_000,
  description:
    "Code review specialist. Judges implementation quality: correctness bugs, unhandled error paths, resource leaks, concurrency and state bugs, and clear false positives in the platform's own findings. Delegates here for a code-level pass or to triage existing findings.",
});
