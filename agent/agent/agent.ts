import { defineAgent } from "eve";
import { mockModel } from "eve/evals";

import { fixtureModel } from "./lib/fixture-model";

const provider = process.env.AI_INTEL_LLM_PROVIDER ?? "gateway";
const modelId = process.env.AI_INTEL_MODEL ?? "anthropic/claude-sonnet-4.5";

/**
 * `AI_INTEL_LLM_PROVIDER=mock` swaps in the scripted fixture model, so evals,
 * local reviews, and CI exercise the full agent loop — tools, citations, HITL
 * gates — with no provider credentials. It replaces the deleted Python mock
 * harness.
 */
const model = provider === "mock" ? mockModel(fixtureModel) : modelId;

export default defineAgent({
  model,
  // Declared explicitly: the fixture model has no gateway context-window
  // metadata, and eve needs a known window to plan compaction.
  modelContextWindowTokens: 200_000,
  description:
    "Repository intelligence analyst for AI Engineering Intelligence: answers questions and runs deep reviews over a repository's symbol graph, deterministic findings, and trust layer.",
  reasoning: "medium",
  limits: {
    maxInputTokensPerSession: 2_000_000,
    maxOutputTokensPerSession: 256_000,
  },
});
