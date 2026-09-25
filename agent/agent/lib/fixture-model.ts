/**
 * Deterministic fixture model for evals, local reviews, and CI.
 *
 * Only active when `AI_INTEL_LLM_PROVIDER=mock`. A real model chooses which
 * tools to call; this one follows a script selected by a marker in the user
 * message, so an eval can assert on tool wiring, citations, and HITL gating
 * without provider credentials or nondeterminism.
 *
 * Markers look like `[fixture:graph-answer]`. Without one, the fixture replies
 * plainly, so ad-hoc manual testing still works.
 */

import type { MockModelRequest, MockModelResponder, MockModelResponse } from "eve/evals";

const ANALYSIS_ID = 42;

type Script = (request: MockModelRequest) => MockModelResponse;

/**
 * True on the first turn that carries this marker.
 *
 * `toolResults` is cumulative across the whole prompt, so "have I already called a
 * tool?" cannot be answered from it in a multi-turn session. Counting how many
 * user messages carry the marker is per-marker and stable.
 */
function firstTurnWithMarker(marker: string, request: MockModelRequest): boolean {
  return (
    request.userMessages.filter((message) => message.includes(`[fixture:${marker}]`)).length === 1
  );
}

/**
 * The last tool result's text, lowercased. Lets a script tell a completed call
 * from a denied or failed one, so a demo never reports success for an action a
 * human just refused.
 */
function lastToolText(request: MockModelRequest): string {
  const results = request.messages.filter((message) => message.role === "tool");
  return (results[results.length - 1]?.text ?? "").toLowerCase();
}

/**
 * How many tool results belong to the current turn: the `tool` messages that
 * follow the last `user` message. This is the step index inside one turn, and it
 * is what a tool-calling script needs — earlier turns' results must not count.
 */
function currentTurnStep(request: MockModelRequest): number {
  let lastUser = -1;
  for (let index = request.messages.length - 1; index >= 0; index -= 1) {
    if (request.messages[index]?.role === "user") {
      lastUser = index;
      break;
    }
  }
  return request.messages.slice(lastUser + 1).filter((message) => message.role === "tool").length;
}

const CITED_FINDING = {
  claim: "Cache keys are salted with a hardcoded SHA1 value.",
  evidence: "build_cache_key assigns a literal salt at app/cache_key.py:11.",
  file_path: "app/cache_key.py",
  line_start: 11,
  line_end: 11,
  severity: "high" as const,
  confidence: 0.6,
  category: "secret",
};

const UNCitedFinding = {
  claim: "Authentication can probably be bypassed somewhere.",
  evidence: "It felt wrong when I read the auth module.",
  severity: "critical" as const,
  confidence: 0.9,
  category: "injection",
};

/**
 * Runs a scripted sequence of tool steps for one turn, then answers.
 *
 * `plan[i]` is the model response for step `i` of the current turn, so a script
 * can require several tools in sequence (find a symbol, then read it). Steps are
 * counted from the prompt, not from `toolResults`, which is cumulative across the
 * whole session and would let an earlier turn satisfy the next turn's first step.
 */
function steps(
  marker: string,
  request: MockModelRequest,
  plan: readonly MockModelResponse[],
  final: string,
): MockModelResponse {
  if (!firstTurnWithMarker(marker, request)) return { text: final };
  return plan[currentTurnStep(request)] ?? { text: final };
}

const SCRIPTS: Record<string, Script> = {
  "graph-answer": (request) =>
    steps(
      "graph-answer",
      request,
      [{ toolCalls: [{ name: "get_analysis", input: { analysisId: ANALYSIS_ID } }] }],
      "Analysis 42 is done: 3 findings, overall 71, published.",
    ),

  "graph-drilldown": (request) =>
    steps(
      "graph-drilldown",
      request,
      [
        { toolCalls: [{ name: "find_symbols", input: { analysisId: ANALYSIS_ID, query: "auth" } }] },
        {
          toolCalls: [
            {
              name: "read_source",
              input: { analysisId: ANALYSIS_ID, path: "app/auth.py", lineStart: 12, context: 3 },
            },
          ],
        },
      ],
      "authenticate lives at app/auth.py:12 and validates before hashing.",
    ),

  "cited-finding": (request) =>
    steps(
      "cited-finding",
      request,
      [
        {
          toolCalls: [
            {
              name: "record_finding",
              input: {
                analysisId: ANALYSIS_ID,
                agent: "eve:security",
                findings: [CITED_FINDING],
                summary: "one confirmed issue",
              },
            },
          ],
        },
      ],
      "Recorded 1 finding citing app/cache_key.py:11.",
    ),

  "uncited-finding": (request) =>
    steps(
      "uncited-finding",
      request,
      [
        {
          toolCalls: [
            {
              name: "record_finding",
              input: {
                analysisId: ANALYSIS_ID,
                agent: "eve:security",
                findings: [UNCitedFinding],
                summary: "unverified hunch",
              },
            },
          ],
        },
      ],
      "That claim had no citation, so it was not recorded.",
    ),

  "run-analysis": (request) => {
    const toolText = lastToolText(request);
    const final = /denied|not approved|cancel/.test(toolText)
      ? "Understood — I did not start an analysis. Say the word if you want one."
      : "Started analysis 43; it is running.";
    return steps("run-analysis", request, [
      { toolCalls: [{ name: "run_analysis", input: { repositoryId: 7 } }] },
    ], final);
  },

  "decide-finding": (request) => {
    const toolText = lastToolText(request);
    const final = /denied|not approved|cancel/.test(toolText)
      ? "Understood — I did not record a decision. The finding stays pending."
      : "Recorded the reviewer's approval.";
    return steps(
      "decide-finding",
      request,
      [
        {
          toolCalls: [
            {
              name: "decide_finding",
              input: {
                analysisId: ANALYSIS_ID,
                findingId: 900,
                decision: "approve",
                note: "confirmed",
              },
            },
          ],
        },
      ],
      final,
    );
  },
};

const MARKER = /\[fixture:([a-z-]+)\]/;

export const fixtureModel: MockModelResponder = (request) => {
  if (process.env.EVE_FIXTURE_DEBUG === "1") {
    console.log(
      "[fixture] roles=" +
        request.messages.map((m) => m.role).join(",") +
        " last=" +
        JSON.stringify(request.lastUserMessage),
    );
  }
  const marker = MARKER.exec(request.lastUserMessage ?? "")?.[1];
  const script = marker ? SCRIPTS[marker] : undefined;
  if (script) return script(request);
  return {
    text: `Mock response${marker ? ` (unknown fixture: ${marker})` : ""}: ${
      request.lastUserMessage ?? "(no message)"
    }`,
  };
};

export const FIXTURE_MARKERS = Object.keys(SCRIPTS);
