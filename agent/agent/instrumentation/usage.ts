/**
 * Reports real model usage to the API ledger.
 *
 * eve publishes `model.call.completed` per model call, but the gateway cost (when
 * there is one) arrives later, on `step.attempt.metadata`. The report is therefore
 * held until the step attempt settles, then posted once with the provider cost if
 * one was reported, or with a token-price estimate otherwise. The event's
 * idempotency key is the ledger's primary key, so a replayed report is a no-op.
 *
 * opencode-go does not expose a cost field through the OpenAI-compatible AI SDK,
 * which is why `RETRACT_LLM_INPUT_COST_PER_MTOK` / `OUTPUT_COST_PER_MTOK` are the
 * authoritative prices for that provider. If they are unset the report still
 * carries tokens, and the API's token ceiling is the fallback.
 *
 * Every failure here is swallowed with a warning: accounting must never be the
 * reason a user cannot get an answer. The provider key's own budget is the final
 * hard stop.
 */

import { defineInstrumentation } from "eve/instrumentation";

import { apiPost } from "../lib/api.ts";

interface PendingCall {
  readonly idempotencyKey: string;
  readonly sessionId: string;
  readonly model: string;
  readonly inputTokens: number;
  readonly outputTokens: number;
  costUsd?: number;
}

/** Model ids by attempt, because the completion event carries only the response id. */
const modelByAttempt = new Map<string, string>();
/** Usage by attempt, held until the step settles so provider cost can be attached. */
const pendingByAttempt = new Map<string, PendingCall>();
/** Gateway cost that arrived before the model-call completion. */
const costByAttempt = new Map<string, number>();

export function tokenCostUsd(
  inputTokens: number,
  outputTokens: number,
  env: Record<string, string | undefined> = process.env,
): number {
  const inputPrice = pricePerMillion(env, "RETRACT_LLM_INPUT_COST_PER_MTOK");
  const outputPrice = pricePerMillion(env, "RETRACT_LLM_OUTPUT_COST_PER_MTOK");
  const cost = (inputTokens / 1_000_000) * inputPrice + (outputTokens / 1_000_000) * outputPrice;
  return Math.round(cost * 1_000_000) / 1_000_000;
}

function pricePerMillion(
  env: Record<string, string | undefined>,
  name: string,
): number {
  const raw = env[name]?.trim();
  if (!raw) return 0;
  const value = Number(raw);
  if (!Number.isFinite(value) || value < 0) {
    throw new Error(`${name} must be a non-negative number (got "${raw}")`);
  }
  return value;
}

/**
 * Read the gateway's reported cost, if this event carries one.
 *
 * The AI SDK's provider metadata shape is provider-specific; only the gateway's
 * `{ gateway: { cost } }` is understood here, and anything else is ignored rather
 * than guessed at.
 */
export function gatewayCostUsd(providerMetadata: unknown): number | undefined {
  if (!providerMetadata || typeof providerMetadata !== "object") return undefined;
  const gateway = (providerMetadata as { gateway?: unknown }).gateway;
  if (!gateway || typeof gateway !== "object") return undefined;
  const raw = (gateway as { cost?: unknown }).cost;
  const value = typeof raw === "string" ? Number(raw) : raw;
  return typeof value === "number" && Number.isFinite(value) && value >= 0 ? value : undefined;
}

async function report(pending: PendingCall, providerCost: number | undefined): Promise<void> {
  const cost = providerCost ?? tokenCostUsd(pending.inputTokens, pending.outputTokens);
  try {
    await apiPost("/api/agent/usage", {
      idempotency_key: pending.idempotencyKey,
      session_id: pending.sessionId,
      model: pending.model,
      input_tokens: pending.inputTokens,
      output_tokens: pending.outputTokens,
      cost_usd: cost,
    });
  } catch (error) {
    console.warn(
      `usage ledger: failed to report ${pending.idempotencyKey}: ${
        error instanceof Error ? error.message : String(error)
      }`,
    );
  }
}

async function settle(attemptId: string): Promise<void> {
  const pending = pendingByAttempt.get(attemptId);
  if (!pending) return;
  const providerCost = pending.costUsd ?? costByAttempt.get(attemptId);
  pendingByAttempt.delete(attemptId);
  modelByAttempt.delete(attemptId);
  costByAttempt.delete(attemptId);
  await report(pending, providerCost);
}

export default defineInstrumentation({
  events: {
    "model.call.started"(event) {
      modelByAttempt.set(event.scope.attemptId, event.model.modelId);
    },

    "model.call.completed"(event) {
      const attemptId = event.scope.attemptId;
      pendingByAttempt.set(attemptId, {
        idempotencyKey: event.idempotencyKey,
        sessionId: event.scope.sessionId,
        model: event.responseModelId ?? modelByAttempt.get(attemptId) ?? "unknown",
        inputTokens: event.usage.inputTokens ?? 0,
        outputTokens: event.usage.outputTokens ?? 0,
      });
    },

    "step.attempt.metadata"(event) {
      const cost = gatewayCostUsd(event.providerMetadata);
      if (cost === undefined) return;
      const pending = pendingByAttempt.get(event.scope.attemptId);
      if (pending) pending.costUsd = cost;
      else costByAttempt.set(event.scope.attemptId, cost);
    },

    async "step.attempt.completed"(event) {
      await settle(event.scope.attemptId);
    },

    // A failed attempt can still contain a model call that was paid for. Report
    // whatever completed rather than dropping it.
    async "step.attempt.failed"(event) {
      await settle(event.scope.attemptId);
    },
  },
});
