/**
 * Per-session model caps, resolved from the environment at build time.
 *
 * eve compiles the agent definition, so these values are frozen into the built
 * image. The Dockerfile receives them as build args and compose passes the same
 * values at run time; changing them requires rebuilding the agent.
 *
 * They are the second layer of spend control: the monthly ledger in the API stops
 * an account after $2 or $10, and these stop one runaway conversation long before
 * that. A cap of `false` is deliberately not supported — a demo deployment should
 * not be able to silently disable its own ceiling.
 */

export interface SessionLimits {
  readonly maxInputTokensPerSession: number;
  readonly maxOutputTokensPerSession: number;
  readonly maxTokenCostUsdPerSession: number;
}

export const DEFAULT_SESSION_LIMITS: SessionLimits = {
  maxInputTokensPerSession: 200_000,
  maxOutputTokensPerSession: 50_000,
  maxTokenCostUsdPerSession: 0.5,
};

function readPositiveNumber(
  env: Record<string, string | undefined>,
  name: string,
  fallback: number,
  integer: boolean,
): number {
  const raw = env[name]?.trim();
  if (!raw) return fallback;
  const value = Number(raw);
  if (!Number.isFinite(value) || value <= 0 || (integer && !Number.isInteger(value))) {
    throw new Error(
      `${name} must be a positive ${integer ? "integer" : "number"} (got "${raw}"). ` +
        "These are eve build inputs; rebuild the agent after changing them.",
    );
  }
  return value;
}

/**
 * Read the caps, or fail at startup with the variable that is wrong.
 *
 * A silently ignored typo here is a silently uncapped session, so invalid values
 * refuse to boot rather than falling back to a default.
 */
export function resolveSessionLimits(
  env: Record<string, string | undefined> = process.env,
): SessionLimits {
  return {
    maxInputTokensPerSession: readPositiveNumber(
      env,
      "RETRACT_AGENT_MAX_INPUT_TOKENS",
      DEFAULT_SESSION_LIMITS.maxInputTokensPerSession,
      true,
    ),
    maxOutputTokensPerSession: readPositiveNumber(
      env,
      "RETRACT_AGENT_MAX_OUTPUT_TOKENS",
      DEFAULT_SESSION_LIMITS.maxOutputTokensPerSession,
      true,
    ),
    maxTokenCostUsdPerSession: readPositiveNumber(
      env,
      "RETRACT_AGENT_MAX_COST_USD",
      DEFAULT_SESSION_LIMITS.maxTokenCostUsdPerSession,
      false,
    ),
  };
}
