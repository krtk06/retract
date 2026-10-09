/**
 * Gate for the live answer-quality evals.
 *
 * These grade *answers*, so they are only meaningful against a real model. Shared
 * by both cases in this directory: a duplicated gate is two gates to forget, and
 * the one thing it must never do is quietly pass.
 *
 * The trap this exists to close: `npm run eval` pins `RETRACT_LLM_PROVIDER=mock`
 * as an inline assignment, which *overrides* whatever the shell exported. So a
 * documented `RETRACT_LLM_PROVIDER=gateway npm run eval -- quality` runs the
 * fixture model anyway. `RETRACT_EVAL_LIVE=1` then forces the suite to run, and a
 * judge model grades a scripted transcript — which grades as `true` for citing
 * `file:line`, because the script was written to. A green result that means
 * nothing is worse than a skip, so that combination is refused outright.
 */

const SKIP_REASON =
  "answer-quality evals need a real model. Run: RETRACT_LLM_PROVIDER=gateway " +
  "AI_GATEWAY_API_KEY=... npm run eval:live -- quality";

function provider(): string {
  return process.env.RETRACT_LLM_PROVIDER ?? "gateway";
}

/**
 * Whether the *chosen* provider has the credential it actually reads.
 *
 * Provider-specific on purpose. `agent.ts` reads `AI_GATEWAY_API_KEY` for
 * `gateway` and `RETRACT_API_KEY ?? OPENAI_API_KEY` for `openai`, and the two are
 * not interchangeable. Accepting either one regardless would let a run pass this
 * gate and then fail inside the model call — which is how an OpenAI key parked in
 * `AI_GATEWAY_API_KEY` survives until it 500s in production, looking configured the
 * whole time.
 */
function credentialFor(name: string): boolean {
  if (name === "openai") return Boolean(process.env.RETRACT_API_KEY || process.env.OPENAI_API_KEY);
  return Boolean(process.env.AI_GATEWAY_API_KEY);
}

export function liveGate(t: { skip: (reason: string) => void }): void {
  const forced = process.env.RETRACT_EVAL_LIVE === "1";
  const name = provider();

  if (name === "mock") {
    if (forced) {
      // Refuse rather than skip: the run asked for live grading and cannot deliver
      // it. A skip here would report success for a suite that never ran.
      throw new Error(
        "RETRACT_EVAL_LIVE=1 but the agent is running the deterministic mock " +
          "provider, so a judge would be grading a scripted transcript. " +
          "Use `npm run eval:live` — it does not pin the provider to mock — and " +
          "export a real one.",
      );
    }
    t.skip(SKIP_REASON);
    return;
  }

  if (!credentialFor(name)) {
    const variable =
      name === "openai" ? "RETRACT_API_KEY (or OPENAI_API_KEY)" : "AI_GATEWAY_API_KEY";
    if (forced) {
      // Named explicitly, because "no credential" is otherwise reported from deep
      // inside a model call that cannot tell which of the two it wanted.
      throw new Error(
        `RETRACT_LLM_PROVIDER=${name} requires ${variable}, which is not set. The ` +
          "two provider credentials are not interchangeable: an OpenAI key in " +
          "AI_GATEWAY_API_KEY (or a gateway key in RETRACT_API_KEY) is rejected.",
      );
    }
    t.skip(SKIP_REASON);
    return;
  }

  if (!forced) {
    // A credential is present but live grading was not requested. Skip rather than
    // spend tokens unasked.
    t.skip(SKIP_REASON);
  }
}