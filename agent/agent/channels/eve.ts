import { jwtHmac, localDev, none } from "eve/channels/auth";
import { defaultEveAuth, eveChannel } from "eve/channels/eve";

import { apiGet, apiPost } from "../lib/api";

/**
 * The browser's session cookie is httpOnly, so the frontend exchanges it for a
 * short-lived HS256 bearer token (`POST /api/auth/eve-token`) and sends that as
 * `Authorization: Bearer`. The backend mints `iss=ai-intel`, `aud=eve-agent`,
 * so neither token can be replayed against the other service.
 */
const secret = process.env.RETRACT_JWT_SECRET;

const auth = secret
  ? [
      jwtHmac({
        algorithm: "HS256",
        audiences: ["eve-agent"],
        issuer: "ai-intel",
        secret,
      }),
      localDev(),
    ]
  : process.env.NODE_ENV === "production"
    ? // Fail closed: without a shared secret no production caller can be verified.
      [localDev()]
    : [localDev(), none()];

interface Principal {
  readonly subject?: string;
}

interface Budget {
  readonly period: string;
  readonly remaining_usd: number;
  readonly remaining_tokens: number | null;
}

/**
 * The account id behind an authenticated caller.
 *
 * eve's `principalId` is the issuer-prefixed form (`ai-intel:123`), which is not a
 * user id the API accepts. The JWT subject is the numeric id, and only that can
 * be mapped to a budget. A local-dev principal has no subject, so it is unmapped
 * rather than charged to an arbitrary account.
 */
function numericUserId(principal: Principal | null | undefined): number | undefined {
  const subject = principal?.subject?.trim();
  if (!subject || !/^\d+$/.test(subject)) return undefined;
  const id = Number(subject);
  return Number.isSafeInteger(id) && id > 0 ? id : undefined;
}

function formatPeriod(period: string): string {
  const [year, month] = period.split("-").map(Number);
  if (!year || !month) return period;
  return new Date(Date.UTC(year, month - 1, 1)).toLocaleString("en-US", {
    month: "long",
    year: "numeric",
    timeZone: "UTC",
  });
}

async function mapSession(
  sessionId: string,
  sessionAuth: {
    readonly current: Principal | null;
    readonly initiator: Principal | null;
  },
): Promise<void> {
  const userId = numericUserId(sessionAuth.current ?? sessionAuth.initiator);
  if (userId === undefined) return;
  try {
    await apiPost("/api/agent/sessions", { session_id: sessionId, user_id: userId });
  } catch (error) {
    // The budget check and the ledger both fail open; a bookkeeping outage must
    // not stop a conversation. The provider key's budget remains the hard stop.
    console.warn(
      `agent budget: could not map session ${sessionId}: ${
        error instanceof Error ? error.message : String(error)
      }`,
    );
  }
}

async function checkBudget(userId: number): Promise<void> {
  let budget: Budget;
  try {
    budget = await apiGet<Budget>("/api/agent/budget", { query: { user_id: userId } });
  } catch (error) {
    console.warn(
      `agent budget: check failed for user ${userId}; allowing the turn: ${
        error instanceof Error ? error.message : String(error)
      }`,
    );
    return;
  }

  if (budget.remaining_usd <= 0) {
    throw new Error(
      `LLM budget exhausted for ${formatPeriod(budget.period)}. ` +
        "Your monthly allowance has been used; it resets on the first of next month (UTC).",
    );
  }
  if (budget.remaining_tokens !== null && budget.remaining_tokens <= 0) {
    throw new Error(
      `LLM token budget exhausted for ${formatPeriod(budget.period)}. ` +
        "Your monthly allowance has been used; it resets on the first of next month (UTC).",
    );
  }
}

export default eveChannel({
  auth,
  onMessage: async (ctx) => {
    const userId = numericUserId(ctx.eve.caller);
    if (userId !== undefined) {
      // Before dispatch: this is the user-facing stop. A turn already in flight
      // is bounded by eve's per-session token cap instead.
      await checkBudget(userId);
    }
    return { auth: defaultEveAuth(ctx) };
  },
  events: {
    // Root sessions and subagent child sessions both start a turn. Mapping every
    // one of them to the same account is what makes a subagent's model calls count
    // against the user who dispatched it.
    "turn.started": async (_data, _channel, ctx) => {
      await mapSession(ctx.session.id, ctx.session.auth);
    },
  },
});
