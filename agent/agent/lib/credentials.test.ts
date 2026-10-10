import { strict as assert } from "node:assert";
import { describe, it } from "node:test";

import {
  resolveApiMode,
  resolveBaseUrl,
  resolveCredential,
  resolveHeaders,
  resolveModelId,
} from "./credentials.ts";

// The throw cases matter more than the nested pass cases: a wrong credential is
// silent until the first message is sent, so this function's value is entirely in
// what it stops a deployment from doing.
describe("resolveCredential", () => {
  const OPENAI_KEY = "sk-proj-real-looking-key";
  const GATEWAY_KEY = "a1b2c3d4_9f8e7d6c5b4a";

  describe("openai", () => {
    it("accepts a real-shaped key", () => {
      assert.equal(resolveCredential("openai", { RETRACT_API_KEY: OPENAI_KEY }), OPENAI_KEY);
    });

    it("falls back to OPENAI_API_KEY", () => {
      assert.equal(resolveCredential("openai", { OPENAI_API_KEY: OPENAI_KEY }), OPENAI_KEY);
    });

    it("rejects a missing key, naming the variable", () => {
      assert.throws(
        () => resolveCredential("openai", {}),
        /requires RETRACT_API_KEY \(or OPENAI_API_KEY\)/,
      );
    });

    it("rejects the placeholder this codebase shipped", () => {
      assert.throws(
        () => resolveCredential("openai", { RETRACT_API_KEY: "local-verification-placeholder" }),
        /placeholder value/,
      );
    });

    it("rejects whitespace-only and empty strings", () => {
      for (const bad of ["", "   "]) {
        assert.throws(
          () => resolveCredential("openai", { RETRACT_API_KEY: bad }),
          /requires RETRACT_API_KEY/,
        );
      }
    });
  });

  describe("gateway", () => {
    it("accepts a real-shaped key", () => {
      assert.equal(resolveCredential("gateway", { AI_GATEWAY_API_KEY: GATEWAY_KEY }), GATEWAY_KEY);
    });

    it("rejects an OpenAI key, which is the swap this check exists to catch", () => {
      assert.throws(
        () => resolveCredential("gateway", { AI_GATEWAY_API_KEY: OPENAI_KEY }),
        /looks like an OpenAI key/,
      );
    });

    it("rejects a missing key, naming the variable", () => {
      assert.throws(() => resolveCredential("gateway", {}), /requires AI_GATEWAY_API_KEY/);
    });

    it("rejects a placeholder", () => {
      assert.throws(
        () => resolveCredential("gateway", { AI_GATEWAY_API_KEY: "change-me" }),
        /placeholder value/,
      );
    });
  });

  describe("mock", () => {
    // Needs no credential, and must not be blocked here: the production refusal
    // for mock lives in agent.ts, where NODE_ENV is known.
    it("needs nothing", () => {
      assert.equal(resolveCredential("mock", {}), "");
    });
  });
});

describe("resolveModelId", () => {
  it("falls back when unset", () => {
    assert.equal(resolveModelId({}, "gpt-5"), "gpt-5");
  });

  it("falls back when blank — the case that 404'd as model ``", () => {
    // `.env` writes `RETRACT_MODEL=` as an empty string, which `??` does not
    // treat as unset, so the provider received the literal model id "".
    assert.equal(resolveModelId({ RETRACT_MODEL: "" }, "gpt-5"), "gpt-5");
    assert.equal(resolveModelId({ RETRACT_MODEL: "   " }, "gpt-5"), "gpt-5");
  });

  it("uses an explicit model id", () => {
    assert.equal(resolveModelId({ RETRACT_MODEL: "openai/gpt-5-mini" }, "gpt-5"), "openai/gpt-5-mini");
  });
});

describe("resolveBaseUrl", () => {
  const ZEN = "https://opencode.ai/zen/go/v1";

  it("returns undefined when unset or blank (default OpenAI endpoint)", () => {
    assert.equal(resolveBaseUrl({}), undefined);
    assert.equal(resolveBaseUrl({ RETRACT_LLM_BASE_URL: "  " }), undefined);
  });

  it("normalizes trailing slashes so the SDK never builds //chat/completions", () => {
    assert.equal(resolveBaseUrl({ RETRACT_LLM_BASE_URL: `${ZEN}//` }), ZEN);
  });

  it("accepts an OpenAI-compatible endpoint", () => {
    assert.equal(resolveBaseUrl({ RETRACT_LLM_BASE_URL: ZEN }), ZEN);
    assert.equal(
      resolveBaseUrl({ RETRACT_LLM_BASE_URL: "https://api.experientiallabs.ai/v1" }),
      "https://api.experientiallabs.ai/v1",
    );
  });

  it("accepts opencode-go and OpenAI alike — the SDK holds the key at call time", () => {
    // Verified against a real compiled manifest: eve bakes only the model-id string,
    // never the key or the base URL, so a credential-bearing host here is safe. The
    // base URL is validated for shape and transport, not refused.
    assert.equal(resolveBaseUrl({ RETRACT_LLM_BASE_URL: ZEN }), ZEN);
    assert.equal(resolveBaseUrl({ RETRACT_LLM_BASE_URL: "https://api.openai.com/v1" }), "https://api.openai.com/v1");
    assert.equal(resolveBaseUrl({ RETRACT_LLM_BASE_URL: "https://openrouter.ai/api/v1" }), "https://openrouter.ai/api/v1");
  });

  it("rejects malformed URLs", () => {
    assert.throws(
      () => resolveBaseUrl({ RETRACT_LLM_BASE_URL: "not-a-url" }),
      /not a valid URL/,
    );
  });

  it("rejects plaintext http off localhost", () => {
    assert.throws(
      () => resolveBaseUrl({ RETRACT_LLM_BASE_URL: "http://example.com/v1" }),
      /must use https/,
    );
  });

  it("allows http on localhost for local servers", () => {
    assert.equal(
      resolveBaseUrl({ RETRACT_LLM_BASE_URL: "http://localhost:8000/v1" }),
      "http://localhost:8000/v1",
    );
  });
});

describe("resolveApiMode", () => {
  it("defaults to chat, because most compatible gateways serve /chat/completions", () => {
    assert.equal(resolveApiMode({}), "chat");
    assert.equal(resolveApiMode({ RETRACT_LLM_API_MODE: "" }), "chat");
  });

  it("accepts responses explicitly", () => {
    assert.equal(resolveApiMode({ RETRACT_LLM_API_MODE: "responses" }), "responses");
    assert.equal(resolveApiMode({ RETRACT_LLM_API_MODE: "CHAT" }), "chat");
  });

  it("rejects anything else", () => {
    assert.throws(
      () => resolveApiMode({ RETRACT_LLM_API_MODE: "completions" }),
      /must be "chat" or "responses"/,
    );
  });
});

describe("openai against a custom endpoint", () => {
  it("prefers RETRACT_LLM_API_KEY when a base URL is set", () => {
    // The custom endpoint brings its own key convention, so the dedicated variable
    // wins over the OpenAI-shaped one.
    const key = resolveCredential("openai", {
      RETRACT_LLM_BASE_URL: "https://api.experientiallabs.ai/v1",
      RETRACT_LLM_API_KEY: "poppy-key",
      RETRACT_API_KEY: "sk-proj-decoy",
    });
    assert.equal(key, "poppy-key");
  });

  it("accepts a non-sk key on a custom endpoint", () => {
    // opencode-go keys are not `sk-` prefixed; the shape check must not fire.
    const key = resolveCredential("openai", {
      RETRACT_LLM_BASE_URL: "https://api.experientiallabs.ai/v1",
      RETRACT_LLM_API_KEY: "go-key-that-does-not-start-with-sk",
    });
    assert.equal(key, "go-key-that-does-not-start-with-sk");
  });

  it("still refuses a missing key on a custom endpoint", () => {
    assert.throws(
      () =>
        resolveCredential("openai", {
          RETRACT_LLM_BASE_URL: "https://api.experientiallabs.ai/v1",
        }),
      /requires RETRACT_LLM_API_KEY/,
    );
  });
});

// opencode-go refuses a request with no `x-opencode-session` header, so a
// missing one is not cosmetic: it fails every model call with an upstream error
// that names no variable. This exists to make that header a first-class,
// validated setting rather than a comment in a dotenv file.
describe("resolveHeaders", () => {
  const CUSTOM = { RETRACT_LLM_BASE_URL: "https://opencode.ai/zen/go/v1" };

  it("returns undefined for plain OpenAI, so the real endpoint is untouched", () => {
    assert.equal(resolveHeaders({}), undefined);
  });

  it("gives a custom endpoint a self-identifying user agent", () => {
    assert.deepEqual(resolveHeaders(CUSTOM), { "user-agent": "retract-agent/0.1.0" });
  });

  it("passes the opencode session header through", () => {
    assert.deepEqual(
      resolveHeaders({
        ...CUSTOM,
        RETRACT_LLM_HEADERS: '{"x-opencode-session":"retract-dev"}',
      }),
      { "user-agent": "retract-agent/0.1.0", "x-opencode-session": "retract-dev" },
    );
  });

  it("lets an explicit user agent win over the default", () => {
    const headers = resolveHeaders({
      ...CUSTOM,
      RETRACT_LLM_HEADERS: '{"user-agent":"my-agent/1.0"}',
    });
    assert.ok(headers, "headers should resolve for a custom endpoint");
    assert.equal(headers["user-agent"], "my-agent/1.0");
  });

  it("survives the .env round trip, where bash strips bare quotes", () => {
    // What `set -a; source .env` actually produces for the single-quoted form.
    const sourced = { ...CUSTOM, RETRACT_LLM_HEADERS: '{"x-opencode-session":"retract-dev"}' };
    const headers = resolveHeaders(sourced);
    assert.ok(headers, "headers should resolve for a custom endpoint");
    assert.equal(headers["x-opencode-session"], "retract-dev");
  });

  it("rejects malformed JSON, naming the shape", () => {
    assert.throws(
      () => resolveHeaders({ ...CUSTOM, RETRACT_LLM_HEADERS: "{x-opencode-session:retract-dev}" }),
      /not valid JSON/,
    );
  });

  it("rejects a list, which would send a header named 0", () => {
    assert.throws(
      () => resolveHeaders({ ...CUSTOM, RETRACT_LLM_HEADERS: '["x-opencode-session"]' }),
      /must be a JSON object/,
    );
  });

  it("rejects a non-string value rather than sending [object Object]", () => {
    assert.throws(
      () => resolveHeaders({ ...CUSTOM, RETRACT_LLM_HEADERS: '{"x-retry":3}' }),
      /must be a string/,
    );
  });
});
