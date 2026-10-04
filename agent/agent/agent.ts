import { createOpenAI } from "@ai-sdk/openai";
import { defineAgent } from "eve";
import { mockModel } from "eve/evals";

import { fixtureModel } from "./lib/fixture-model";

/**
 * Model selection, driven entirely by the environment.
 *
 *   AI_INTEL_LLM_PROVIDER=mock      deterministic fixture model — no credentials,
 *                                    used by CI, evals, and offline review
 *   AI_INTEL_LLM_PROVIDER=openai    a real OpenAI key via the AI SDK provider
 *   AI_INTEL_LLM_PROVIDER=gateway   anything else, by id, through the Vercel AI
 *                                    Gateway (the default)
 *
 * A direct provider needs its AI SDK package installed, which is why
 * `@ai-sdk/openai` is a dependency rather than an optional peer: `eve start` must
 * not fail at import time on a host that only ever runs the mock.
 */
const provider = process.env.AI_INTEL_LLM_PROVIDER ?? "gateway";

function resolveModel() {
  if (provider === "mock") {
    // The fixture model answers from canned transcripts, so a deployment left on it
    // looks entirely healthy while every finding and claim is invented. `.env.example`
    // ships `mock` because the offline dev quickstart needs no credentials, which
    // makes this the single most likely production misconfiguration. Refuse it.
    if (process.env.NODE_ENV === "production") {
      throw new Error(
        "AI_INTEL_LLM_PROVIDER=mock is a deterministic fixture model and must not " +
          "run in production; use gateway (the default) or openai. If you copied " +
          ".env.example unchanged, set AI_INTEL_LLM_PROVIDER=gateway.",
      );
    }
    return mockModel(fixtureModel);
  }
  if (provider === "openai") {
    const apiKey = process.env.AI_INTEL_API_KEY ?? process.env.OPENAI_API_KEY;
    if (!apiKey) {
      throw new Error(
        "AI_INTEL_LLM_PROVIDER=openai requires AI_INTEL_API_KEY (or OPENAI_API_KEY)",
      );
    }
    return createOpenAI({ apiKey })(process.env.AI_INTEL_MODEL ?? "gpt-5");
  }
  return process.env.AI_INTEL_MODEL ?? "anthropic/claude-sonnet-4.5";
}

export default defineAgent({
  model: resolveModel(),
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
