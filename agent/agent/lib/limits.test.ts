import { strict as assert } from "node:assert";
import { describe, it } from "node:test";

import { DEFAULT_SESSION_LIMITS, resolveSessionLimits } from "./limits.ts";

describe("resolveSessionLimits", () => {
  it("uses conservative demo-safe defaults when nothing is set", () => {
    assert.deepEqual(resolveSessionLimits({}), DEFAULT_SESSION_LIMITS);
  });

  it("accepts overrides from the environment", () => {
    assert.deepEqual(
      resolveSessionLimits({
        RETRACT_AGENT_MAX_INPUT_TOKENS: "100000",
        RETRACT_AGENT_MAX_OUTPUT_TOKENS: "20000",
        RETRACT_AGENT_MAX_COST_USD: "0.10",
      }),
      {
        maxInputTokensPerSession: 100_000,
        maxOutputTokensPerSession: 20_000,
        maxTokenCostUsdPerSession: 0.1,
      },
    );
  });

  it("rejects a non-numeric cap instead of silently leaving the session uncapped", () => {
    assert.throws(
      () => resolveSessionLimits({ RETRACT_AGENT_MAX_INPUT_TOKENS: "lots" }),
      /RETRACT_AGENT_MAX_INPUT_TOKENS must be a positive integer/,
    );
  });

  it("rejects a fractional token cap and a non-positive cost cap", () => {
    assert.throws(
      () => resolveSessionLimits({ RETRACT_AGENT_MAX_OUTPUT_TOKENS: "1.5" }),
      /positive integer/,
    );
    assert.throws(
      () => resolveSessionLimits({ RETRACT_AGENT_MAX_COST_USD: "0" }),
      /positive number/,
    );
  });
});
