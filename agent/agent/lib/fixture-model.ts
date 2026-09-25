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

const SCRIPTS: Record<string, Script> = {
  "graph-answer": (request) =>
    request.toolResults.length === 0
      ? { toolCalls: [{ name: "get_analysis", input: { analysisId: ANALYSIS_ID } }] }
      : { text: "Analysis 42 is done: 3 findings, overall 71, published." },

  "graph-drilldown": (request) =>
    request.toolResults.length === 0
      ? { toolCalls: [{ name: "find_symbols", input: { analysisId: ANALYSIS_ID, query: "auth" } }] }
      : request.toolResults.length === 1
        ? {
            toolCalls: [
              {
                name: "read_source",
                input: { analysisId: ANALYSIS_ID, path: "app/auth.py", lineStart: 12, context: 3 },
              },
            ],
          }
        : { text: "authenticate lives at app/auth.py:12 and validates before hashing." },

  "cited-finding": (request) =>
    request.toolResults.length === 0
      ? {
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
        }
      : { text: "Recorded 1 finding citing app/cache_key.py:11." },

  "uncited-finding": (request) =>
    request.toolResults.length === 0
      ? {
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
        }
      : { text: "That claim had no citation, so it was not recorded." },

  "run-analysis": (request) =>
    request.toolResults.length === 0
      ? { toolCalls: [{ name: "run_analysis", input: { repositoryId: 7 } }] }
      : { text: "Started analysis 43; it is running." },

  "decide-finding": (request) =>
    request.toolResults.length === 0
      ? {
          toolCalls: [
            {
              name: "decide_finding",
              input: { analysisId: ANALYSIS_ID, findingId: 900, decision: "approve", note: "confirmed" },
            },
          ],
        }
      : { text: "Recorded the reviewer's approval." },
};

const MARKER = /\[fixture:([a-z-]+)\]/;

export const fixtureModel: MockModelResponder = (request) => {
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
