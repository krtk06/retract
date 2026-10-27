import { strict as assert } from "node:assert";
import { describe, it } from "node:test";

import { gatewayCostUsd, tokenCostUsd } from "./usage.ts";

describe("tokenCostUsd", () => {
  it("prices input and output tokens independently", () => {
    // 1M input at $0.25, 2M output at $1.50.
    assert.equal(
      tokenCostUsd(1_000_000, 2_000_000, {
        RETRACT_LLM_INPUT_COST_PER_MTOK: "0.25",
        RETRACT_LLM_OUTPUT_COST_PER_MTOK: "1.50",
      }),
      3.25,
    );
  });

  it("rounds to the ledger's six-decimal precision", () => {
    assert.equal(
      tokenCostUsd(1, 1, {
        RETRACT_LLM_INPUT_COST_PER_MTOK: "0.25",
        RETRACT_LLM_OUTPUT_COST_PER_MTOK: "0.25",
      }),
      0.000001,
    );
  });

  it("reports zero when no prices are configured, leaving tokens as the fallback", () => {
    assert.equal(tokenCostUsd(1_000, 2_000, {}), 0);
  });

  it("refuses a malformed price instead of silently dropping the dollar ledger", () => {
    assert.throws(
      () =>
        tokenCostUsd(1, 1, {
          RETRACT_LLM_INPUT_COST_PER_MTOK: "free",
        }),
      /must be a non-negative number/,
    );
  });
});

describe("gatewayCostUsd", () => {
  it("reads the gateway's numeric or string cost", () => {
    assert.equal(gatewayCostUsd({ gateway: { cost: 0.0123 } }), 0.0123);
    assert.equal(gatewayCostUsd({ gateway: { cost: "0.5" } }), 0.5);
  });

  it("ignores metadata from providers that do not report a cost", () => {
    assert.equal(gatewayCostUsd({ opencode: { list_cost: 0.01 } }), undefined);
    assert.equal(gatewayCostUsd({ gateway: { cost: "not-a-number" } }), undefined);
    assert.equal(gatewayCostUsd({ gateway: { cost: -1 } }), undefined);
    assert.equal(gatewayCostUsd(undefined), undefined);
  });
});
