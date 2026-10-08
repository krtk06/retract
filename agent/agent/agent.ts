import { createOpenAI } from "@ai-sdk/openai";
import { defineAgent } from "eve";
import { mockModel } from "eve/evals";

import {
  resolveApiMode,
  resolveBaseUrl,
  resolveCredential,
  resolveModelId,
} from "./lib/credentials";
import { fixtureModel } from "./lib/fixture-model";

/**
 * Model selection, driven entirely by the environment.
 *
 *   AI_INTEL_LLM_PROVIDER=mock      deterministic fixture model — no credentials,
 *                                    used by CI, evals, and offline review
 *   AI_INTEL_LLM_PROVIDER=openai    an OpenAI-compatible endpoint via the AI SDK
 *   AI_INTEL_LLM_PROVIDER=gateway   anything else, by id, through the Vercel AI
 *                                    Gateway (the default)
 *
 * A direct provider needs its AI SDK package installed, which is why
 * `@ai-sdk/openai` is a dependency rather than an optional peer: `eve start` must
 * not fail at import time on a host that only ever runs the mock.
 *
 * `AI_INTEL_LLM_BASE_URL` re-points the `openai` provider at any compatible
 * endpoint — opencode-go, a local vLLM, Ollama — so those need no new dependency
 * and no new provider name. `AI_INTEL_LLM_API_MODE` selects the API shape, because
 * the SDK defaults to the Responses API while most compatible gateways serve
 * `/chat/completions`; defaulting to `chat` avoids a 404 that names no cause.
 *
 * Credentials are resolved by `resolveCredential` (`lib/credentials.ts`), which
 * refuses a missing, placeholder, or wrong-provider key at startup, and by
 * `resolveBaseUrl`, which validates the custom endpoint's shape and transport. A
 * wrong configuration used to surface only on the first message, as an upstream
 * error naming no variable — and the well-meaning `${AI_GATEWAY_API_KEY:?…}` in
 * compose could not be conditional on the provider, so it demanded a key the
 * `openai` provider never reads.
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
    const baseURL = resolveBaseUrl();
    const client = createOpenAI({ apiKey: resolveCredential("openai"), baseURL });
    // With a custom endpoint the host decides the model ids, and `gpt-5` is a guess
    // it is unlikely to serve — so an unset model id becomes an explicit error rather
    // than a confusing "model not found" from the gateway.
    const model = resolveModelId(process.env, baseURL ? "" : "gpt-5");
    if (!model) {
      throw new Error(
        `AI_INTEL_MODEL is required when AI_INTEL_LLM_BASE_URL is set (${baseURL}). ` +
          `The endpoint chooses the model ids; list them at ${baseURL}/models.`,
      );
    }
    // `chat` rather than the provider's default, which is the Responses API. The two
    // differ in wire format, and a compatible gateway that serves `/chat/completions`
    // answers the Responses client with a bare 404.
    return resolveApiMode() === "responses" ? client.responses(model) : client.chat(model);
  }
  // The gateway key is enforced only for a production start on a host, where the
  // environment is runtime env and a missing key is knowable now. Two cases are
  // deliberately excluded, both because eve compiles the resolved model into its
  // build output (see the Dockerfile's known-limitation note):
  //   • a container build — the model is baked here and the key is supplied at run
  //     time, so requiring it at build would fail every image build, including CI's;
  //   • a container at run time — this module is not re-imported, so the check could
  //     not fire anyway; the compiled manifest has already fixed the provider.
  if (process.env.NODE_ENV === "production") {
    resolveCredential("gateway");
  }
  return resolveModelId(process.env, "anthropic/claude-sonnet-4.5");
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
