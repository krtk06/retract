import { defineAgent } from "eve";
import { mockModel } from "eve/evals";

const provider = process.env.AI_INTEL_LLM_PROVIDER ?? "gateway";
const modelId = process.env.AI_INTEL_MODEL ?? "anthropic/claude-sonnet-4.5";

/**
 * `AI_INTEL_LLM_PROVIDER=mock` swaps in a deterministic fixture model, so evals,
 * local reviews, and CI run the full agent loop with no provider credentials.
 * It is the eve replacement for the removed `AI_INTEL_LLM_PROVIDER=mock` harness.
 */
const model =
  provider === "mock"
    ? mockModel(({ lastUserMessage, toolResults }) =>
        toolResults.length === 0
          ? {
              text: `Mock turn for: ${lastUserMessage ?? "(no message)"}`,
            }
          : {
              text: `Mock answer after ${toolResults.length} tool call(s): ${JSON.stringify(toolResults[0]?.output ?? null)}`,
            },
      )
    : modelId;

export default defineAgent({
  model,
  // Declared explicitly: the deterministic mock model has no gateway metadata,
  // and eve needs a known window to plan compaction.
  modelContextWindowTokens: 200_000,
  description:
    "Repository intelligence analyst for AI Engineering Intelligence: answers questions and runs deep reviews over a repository's symbol graph, deterministic findings, and trust layer.",
  reasoning: "medium",
  limits: {
    maxInputTokensPerSession: 2_000_000,
    maxOutputTokensPerSession: 256_000,
  },
});
