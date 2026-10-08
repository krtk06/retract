import { useCallback, useEffect, useMemo, useRef, useState, type ReactNode } from "react";
import { useEveAgent, type EveMessagePart } from "eve/react";

import { useEveToken } from "../api/useEveToken";

/**
 * Chat with the eve agent about one analysis.
 *
 * The panel renders three things, because all three are part of the product:
 * the conversation, which tools the agent actually called (so a claim can be
 * traced to a query), and approval prompts — the agent cannot start an analysis
 * or record a human review decision without a person clicking through here.
 */

type PendingRequest = {
  requestId: string;
  prompt: string;
  kind: string;
  options?: readonly { id: string; label: string }[];
};

const SUGGESTIONS = [
  "What are the biggest risks in this codebase?",
  "Run a security review",
  "Which functions have the most callers?",
];

function pendingApprovals(messages: readonly { parts: readonly EveMessagePart[] }[]): PendingRequest[] {
  return messages
    .flatMap((message) => message.parts)
    .flatMap((part) => {
      if (part.type !== "dynamic-tool" || part.state !== "approval-requested") return [];
      const request = part.toolMetadata?.eve?.inputRequest;
      if (!request || request.kind !== "tool-approval") return [];
      return [
        {
          requestId: request.requestId,
          prompt: request.prompt,
          kind: request.kind,
          options: request.options,
        },
      ];
    });
}

function toolNames(messages: readonly { parts: readonly EveMessagePart[] }[]): string[] {
  const names: string[] = [];
  for (const message of messages) {
    for (const part of message.parts) {
      if (part.type === "dynamic-tool" && !names.includes(part.toolName)) {
        names.push(part.toolName);
      }
    }
  }
  return names;
}

/**
 * Render one projected part. Tool calls are always shown, including failures and
 * denials: a claim the agent could not verify is exactly what a reviewer needs to
 * see, and a silent tool failure reads as a hallucinated answer.
 */
function renderPart(part: EveMessagePart, index: number, role: string): ReactNode {
  if (part.type === "text") {
    if (part.text.trim().length === 0) return null;
    return (
      <p
        key={index}
        className={
          role === "user"
            ? "rounded-lg bg-zinc-800 px-3 py-2 text-sm text-zinc-100"
            : "whitespace-pre-wrap text-sm leading-relaxed text-zinc-300"
        }
      >
        {part.text}
      </p>
    );
  }
  if (part.type === "dynamic-tool") {
    const state = part.state;
    if (state === "output-available") {
      return (
        <p key={index} className="font-mono text-[11px] text-emerald-400/80">
          ✓ {part.toolName}
        </p>
      );
    }
    if (state === "output-error") {
      return (
        <p key={index} className="font-mono text-[11px] text-rose-400/80">
          ✗ {part.toolName} failed{part.errorText ? `: ${part.errorText.slice(0, 120)}` : ""}
        </p>
      );
    }
    if (state === "output-denied") {
      return (
        <p key={index} className="font-mono text-[11px] text-amber-400/80">
          ⊘ {part.toolName} was not approved
        </p>
      );
    }
    if (state === "approval-responded" || state === "input-available" || state === "input-streaming") {
      return (
        <p key={index} className="font-mono text-[11px] text-zinc-500">
          … {part.toolName}
        </p>
      );
    }
    return null;
  }
  return null;
}

export function AgentChat({
  analysisId,
  initialPrompt,
}: {
  analysisId: number;
  // A request handed over by another surface — the fix plan's "deep fix plan"
  // button. It is *pre-filled into the composer*, not sent automatically.
  //
  // Auto-sending it looks more convenient and is not. The eve hook creates a fresh
  // session per mount and attaches/resumes on the way up, so a send issued from an
  // effect races that lifecycle: the optimistic user message appears in the
  // transcript while the turn never reaches the stream, leaving a request that
  // looks sent and gets no answer — and it fails silently, which is the worst way
  // for this to break. Handing over a draft keeps the human in the loop, which is
  // the right default for spending a model's tokens anyway, and it cannot race.
  initialPrompt?: string | null;
}) {
  const { auth, error: authError } = useEveToken();
  const [draft, setDraft] = useState("");
  const [localError, setLocalError] = useState<string | null>(null);
  const logRef = useRef<HTMLDivElement>(null);
  const agent = useEveAgent({
    auth,
    // Turn failures surface here, not in `agent.error`: a failed *model call*
    // arrives as a `step.failed` stream event, which eve's client deliberately
    // does not convert into a snapshot error (only `session.failed` is) and its
    // reducer does not project into a message — so without this a turn that died
    // on, say, an expired key left the user's message on screen with no reply and
    // no explanation, reading exactly like a hang. Surfaced as a panel error, not
    // a transcript entry, because nothing answered.
    onEvent: (event) => {
      if (event.type !== "step.failed" && event.type !== "turn.failed" && event.type !== "session.failed") {
        return;
      }
      const data = event.data as { code?: string; message?: string };
      const label =
        event.type === "step.failed" ? "the model call failed" : `the ${event.type.replace(".", " ")}`;
      setLocalError([label, data.message].filter(Boolean).join(": "));
    },
  });

  const messages = agent.data.messages;
  const approvals = useMemo(() => pendingApprovals(messages), [messages]);
  const called = useMemo(() => toolNames(messages), [messages]);
  const busy = agent.status === "submitted" || agent.status === "streaming";
  const resuming = agent.status === "resuming";

  useEffect(() => {
    logRef.current?.scrollTo({ top: logRef.current.scrollHeight, behavior: "smooth" });
  }, [messages.length, approvals.length]);

  const send = useCallback(
async (text: string) => {
      const message = text.trim();
      if (message.length === 0 || busy || resuming) return;
      setDraft("");
      setLocalError(null);
      // Fire-and-forget: the hook owns the durable session, and `agent.error`
      // carries any later failure back into the panel. Awaiting here would clear
      // the composer's optimistic echo only after the whole turn finished.
      void agent
        .send(message, {
          clientContext: {
            analysisId,
            hint: `The dashboard is showing analysis ${analysisId}. Use its graph and findings tools.`,
          },
        })
        .catch((cause: unknown) => {
          setLocalError(
            cause instanceof Error ? cause.message : "the agent did not accept the message",
          );
        });
    },
    [agent, analysisId, busy, resuming],
  );

  // Adopt a handed-over prompt once. `useState` initialiser rather than an effect:
  // seeding the draft during render means the first paint already shows the
  // request, and switching tabs back and forth never re-seeds a draft the user has
  // since edited.
  const adopted = useRef(false);
  if (initialPrompt && !adopted.current) {
    adopted.current = true;
    if (draft === "") setDraft(initialPrompt);
  }

  if (authError && messages.length === 0) {
    return (
      <section className="rounded-lg border border-amber-900/60 bg-amber-950/30 p-5 text-sm text-amber-200">
        The agent is unavailable: {authError}
      </section>
    );
  }

  return (
    <section className="flex flex-col rounded-lg border border-zinc-800 bg-zinc-900">
      <header className="flex items-center justify-between gap-3 border-b border-zinc-800 px-5 py-3">
        <div>
          <h3 className="font-semibold">Ask the agent</h3>
          <p className="text-xs text-zinc-500">
            Answers cite <code className="text-zinc-400">file:line</code> from this analysis
          </p>
        </div>
        <button
          type="button"
          onClick={() => agent.reset()}
          className="rounded-md border border-zinc-700 px-2.5 py-1 text-xs text-zinc-400 transition hover:border-zinc-600 hover:text-zinc-200"
        >
          New chat
        </button>
      </header>

      {called.length > 0 && (
        <div className="flex flex-wrap gap-1.5 border-b border-zinc-800/70 px-5 py-2">
          {called.map((name) => (
            <span
              key={name}
              className="rounded-full bg-zinc-800 px-2 py-0.5 font-mono text-[11px] text-zinc-400"
            >
              {name}
            </span>
          ))}
        </div>
      )}

      <div ref={logRef} className="max-h-96 min-h-32 space-y-4 overflow-y-auto px-5 py-4">
        {messages.length === 0 && (
          <div className="space-y-2 text-sm text-zinc-500">
            <p>Ask about this analysis, or request a review:</p>
            <div className="flex flex-wrap gap-2">
              {SUGGESTIONS.map((suggestion) => (
                <button
                  key={suggestion}
                  type="button"
                  onClick={() => send(suggestion)}
                  disabled={busy || resuming}
                  className="rounded-full border border-zinc-700 px-3 py-1 text-xs text-zinc-300 transition hover:border-zinc-600 hover:text-zinc-100 disabled:opacity-50"
                >
                  {suggestion}
                </button>
              ))}
            </div>
          </div>
        )}

        {messages.map((message) => {
          const body = message.parts
            .map((part, index) => renderPart(part, index, message.role))
            .filter((node): node is ReactNode => node !== null);
          if (body.length === 0) return null;
          return (
            <article key={message.id} className="space-y-1">
              <p className="text-[11px] uppercase tracking-wide text-zinc-500">{message.role}</p>
              {body}
            </article>
          );
        })}

        {resuming && <p className="text-xs text-zinc-500">Reconnecting to the agent…</p>}
        {localError && <p className="text-xs text-rose-400">{localError}</p>}
        {agent.error && <p className="text-xs text-rose-400">{agent.error.message}</p>}
      </div>

      {approvals.map((approval) => (
        <div
          key={approval.requestId}
          className="border-t border-amber-900/60 bg-amber-950/30 px-5 py-3 text-sm"
        >
          <p className="font-medium text-amber-100">Approval required</p>
          <p className="text-xs text-amber-200/80">{approval.prompt}</p>
          <div className="mt-2 flex gap-2">
            {(approval.options ?? []).map((option) => (
              <button
                key={option.id}
                type="button"
                onClick={() => void agent.respond([{ requestId: approval.requestId, optionId: option.id }])}
                className={`rounded-md px-3 py-1 text-xs font-medium transition ${
                  option.id === "approve"
                    ? "bg-amber-500 text-zinc-950 hover:bg-amber-400"
                    : "border border-amber-800 text-amber-200 hover:bg-amber-950"
                }`}
              >
                {option.label}
              </button>
            ))}
          </div>
        </div>
      ))}

      <form
        onSubmit={(event) => {
          event.preventDefault();
          send(draft);
        }}
        className="flex flex-col gap-2 border-t border-zinc-800 px-5 py-3"
      >
        {adopted.current && draft.trim().length > 0 && (
          <p className="text-[11px] text-zinc-500">
            Requested from the fix plan — review it, edit it, then send.
          </p>
        )}
        <div className="flex items-center gap-2">
        <input
          value={draft}
          onChange={(event) => setDraft(event.target.value)}
          disabled={busy || resuming}
          placeholder="Ask about this analysis…"
          className="flex-1 rounded-md border border-zinc-700 bg-zinc-950 px-3 py-2 text-sm text-zinc-100 placeholder:text-zinc-600 focus:border-zinc-500 focus:outline-none disabled:opacity-60"
        />
        <button
          type="submit"
          disabled={busy || resuming || draft.trim().length === 0}
          className="rounded-md bg-zinc-100 px-4 py-2 text-sm font-medium text-zinc-900 transition hover:bg-white disabled:opacity-40"
        >
          {/* "Reconnecting…" rather than a live-looking "Send": the client attaches
              and resumes its session on mount, and a click in that window is
              swallowed by the busy guard, so a button that looks ready but does
              nothing is the one failure a user cannot explain. */}
          {resuming ? "Reconnecting…" : busy ? "Working…" : "Send"}
        </button>
        </div>
      </form>
    </section>
  );
}
