/**
 * Credential resolution for the LLM provider.
 *
 * Kept apart from `agent.ts` because that module resolves a model as a side effect
 * of being imported, which makes it untestable — and this is the logic most worth
 * testing, since a wrong credential is silent until the first message is sent.
 */

/**
 * Values that stand in for a credential without being one.
 *
 * A blank or placeholder key is not a harmless no-op for a real provider: it looks
 * configured, boots cleanly, and then fails every model call with an upstream error
 * that names no variable. Refusing at startup turns that into one clear message.
 */
const PLACEHOLDER_CREDENTIALS = new Set([
  "local-verification-placeholder",
  "ci-not-a-real-key",
  "change-me",
  "placeholder",
]);

/** OpenAI keys start `sk-`; Vercel gateway keys are `<id>_<hash>`. */
function looksLikeOpenAiKey(key: string): boolean {
  return key.startsWith("sk-");
}

/**
 * Resolve the credential the *chosen* provider actually reads, or throw a message
 * naming what is wrong.
 *
 * Provider-aware on purpose. The two credentials are not interchangeable — an
 * OpenAI key in `AI_GATEWAY_API_KEY` is rejected by the gateway and a gateway key in
 * `RETRACT_API_KEY` is rejected by OpenAI — and neither upstream error names the
 * variable that was misconfigured. They sit adjacent in `.env`, so swapping them is
 * easy and was the actual cause of this check existing.
 *
 * `mock` needs nothing and returns an empty string; it is refused separately in
 * production, where a scripted model pretending to be an analyst is the worse fault.
 */
export function resolveCredential(
  name: string,
  env: Record<string, string | undefined> = process.env,
): string {
  if (name === "mock") return "";

  const isOpenAi = name === "openai";
  const custom = resolveBaseUrl(env);
  // A custom endpoint brings its own key convention, so `RETRACT_LLM_API_KEY` is
  // accepted first and the `sk-` shape check is skipped. Pointing the agent at
  // opencode-go, a local vLLM, or any other OpenAI-compatible host all need this.
  const variables = isOpenAi
    ? custom
      ? ["RETRACT_LLM_API_KEY", "RETRACT_API_KEY", "OPENAI_API_KEY"]
      : ["RETRACT_API_KEY", "OPENAI_API_KEY"]
    : ["AI_GATEWAY_API_KEY"];
  const key = variables.map((variable) => env[variable]?.trim()).find(Boolean);

  if (!key) {
    throw new Error(
      `RETRACT_LLM_PROVIDER=${name} requires ${variables[0]}` +
        `${variables.length > 1 ? ` (or ${variables.slice(1).join(", ")})` : ""}, ` +
        `which is not set. The two provider credentials are not interchangeable: an ` +
        `OpenAI key in AI_GATEWAY_API_KEY, or a gateway key in RETRACT_API_KEY, ` +
        `is rejected.`,
    );
  }

  if (PLACEHOLDER_CREDENTIALS.has(key.toLowerCase())) {
    throw new Error(
      `${variables[0]} is a placeholder value ("${key}"), not a credential. ` +
        `A deployment left on one boots cleanly and then fails every model call, so ` +
        `it is refused at startup instead. Set a real ` +
        `${isOpenAi ? "provider" : "Vercel AI Gateway"} key.`,
    );
  }

  if (isOpenAi && !custom && !looksLikeOpenAiKey(key)) {
    throw new Error(
      `RETRACT_LLM_PROVIDER=openai but RETRACT_API_KEY looks like a Vercel AI ` +
        `Gateway key, not an OpenAI key. Gateway keys are "<id>_<hash>"; OpenAI keys ` +
        `start with "sk-". Only move it here if it came from platform.openai.com.`,
    );
  }
  if (!isOpenAi && looksLikeOpenAiKey(key)) {
    throw new Error(
      `RETRACT_LLM_PROVIDER=gateway but AI_GATEWAY_API_KEY looks like an OpenAI key ` +
        `(starts with "sk-"), which the gateway rejects. Either use it with ` +
        `RETRACT_LLM_PROVIDER=openai and move it to RETRACT_API_KEY, or set a real ` +
        `Vercel AI Gateway key here.`,
    );
  }

  return key;
}

/**
 * A local address, where a key never leaves the machine.
 *
 * Only used to decide whether a base URL is a plain-http local server.
 */
function isLocalHost(hostname: string): boolean {
  return hostname === "localhost" || hostname === "127.0.0.1" || hostname === "::1";
}

/**
 * The OpenAI-compatible base URL, or `undefined` for the default OpenAI endpoint.
 *
 * `RETRACT_LLM_BASE_URL` re-points the `openai` provider at any compatible
 * endpoint — opencode-go (`https://opencode.ai/zen/go/v1`), a local vLLM, Ollama,
 * any gateway — without adding a dependency or a new provider name.
 *
 * Note this does NOT embed the base URL or the key into the image: eve bakes only
 * the resolved model-id string into its build manifest (verified against a real
 * compiled manifest), while `@ai-sdk/openai` holds the key and base URL in memory and
 * sends them per call. So a credential-bearing host is safe here — the URL is only
 * validated for shape and transport, not refused.
 */
export function resolveBaseUrl(
  env: Record<string, string | undefined> = process.env,
): string | undefined {
  const raw = env.RETRACT_LLM_BASE_URL?.trim();
  if (!raw) return undefined;

  let parsed: URL;
  try {
    parsed = new URL(raw);
  } catch {
    throw new Error(
      `RETRACT_LLM_BASE_URL is not a valid URL ("${raw}"). Give the origin, or the ` +
        `origin plus API path, e.g. https://opencode.ai/zen/go/v1.`,
    );
  }
  if (parsed.protocol !== "https:" && !isLocalHost(parsed.hostname)) {
    throw new Error(
      `RETRACT_LLM_BASE_URL must use https ("${raw}"). Plain http would send your ` +
        `key in clear text; http is allowed only for localhost.`,
    );
  }
  // Trailing slashes are normalized away so the SDK never builds `//chat/completions`.
  return raw.replace(/\/+$/, "");
}

/**
 * Which OpenAI API shape the target endpoint speaks.
 *
 * The SDK's default is the Responses API (`/responses`), but most OpenAI-compatible
 * gateways — opencode-go included — serve `/chat/completions`, and pointing the
 * Responses client at those returns a 404 that names no cause. `chat` is therefore
 * the default here, and `responses` is opt-in for the endpoints that want it.
 */
export function resolveApiMode(
  env: Record<string, string | undefined> = process.env,
): "chat" | "responses" {
  const raw = env.RETRACT_LLM_API_MODE?.trim().toLowerCase();
  if (!raw) return "chat";
  if (raw === "chat" || raw === "responses") return raw;
  throw new Error(
    `RETRACT_LLM_API_MODE must be "chat" or "responses" (got "${raw}"). Most ` +
      `OpenAI-compatible endpoints serve /chat/completions; the Responses API is ` +
      `used only by some.`,
  );
}

/**
 * The model id for the provider, falling back when unset *or blank*.
 *
 * `??` is not enough here: `.env` writes `RETRACT_MODEL=` as an empty string, which
 * is not nullish, so a blank value sailed past the fallback and was sent to the
 * provider as the literal model id `""` — a 404 ("The model `` does not exist") that
 * says nothing about the cause. `.env.example` promises that blank takes the
 * default, so that promise is kept here.
 */
export function resolveModelId(
  env: Record<string, string | undefined> = process.env,
  fallback: string,
): string {
  return env.RETRACT_MODEL?.trim() || fallback;
}