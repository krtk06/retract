import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

const { agentState } = vi.hoisted(() => ({
  agentState: { status: "ready" as string, send: vi.fn().mockResolvedValue(undefined) },
}));

// The eve client is stubbed rather than run: these tests are about the handover
// contract between the fix plan and the composer, not about the agent transport.
vi.mock("eve/react", () => ({
  useEveAgent: () => ({
    data: { messages: [] },
    status: agentState.status,
    error: null,
    send: agentState.send,
    respond: vi.fn(),
    reset: vi.fn(),
  }),
}));

vi.mock("../api/useEveToken", () => ({
  useEveToken: () => ({ auth: { bearer: () => Promise.resolve("t") }, error: null }),
}));

import { AgentChat } from "../components/AgentChat";

// jsdom does not implement scrollTo, and the panel scrolls its log into view on
// every render.
Element.prototype.scrollTo = function scrollTo() {};

const REQUEST = "Produce a deep fix plan for this analysis.";

describe("AgentChat prompt handover", () => {
  it("pre-fills the request instead of sending it", () => {
    // Auto-sending races the client's attach/resume and silently drops the turn:
    // the prompt shows in the transcript and no answer ever arrives.
    render(<AgentChat analysisId={1} initialPrompt={REQUEST} />);

    const composer = screen.getByPlaceholderText("Ask about this analysis…");
    expect(composer).toHaveValue(REQUEST);
    expect(agentState.send).not.toHaveBeenCalled();
    expect(screen.getByText(/Requested from the fix plan/)).toBeInTheDocument();
  });

  it("sends the handed-over request when the user submits it", () => {
    render(<AgentChat analysisId={1} initialPrompt={REQUEST} />);

    fireEvent.click(screen.getByRole("button", { name: "Send" }));

    expect(agentState.send).toHaveBeenCalledWith(REQUEST, expect.anything());
    expect(screen.getByPlaceholderText("Ask about this analysis…")).toHaveValue("");
  });

  it("leaves the composer empty when no request was handed over", () => {
    render(<AgentChat analysisId={1} />);
    expect(screen.getByPlaceholderText("Ask about this analysis…")).toHaveValue("");
    expect(screen.queryByText(/Requested from the fix plan/)).not.toBeInTheDocument();
  });

  it("does not re-seed the draft after the user clears it", () => {
    // Switching tabs unmounts and remounts this panel. If the handover re-ran, a
    // cleared composer would silently refill with a request the user rejected.
    const { unmount } = render(<AgentChat analysisId={1} initialPrompt={REQUEST} />);
    fireEvent.click(screen.getByRole("button", { name: "Send" }));
    unmount();

    render(<AgentChat analysisId={1} initialPrompt={REQUEST} />);
    expect(screen.getByPlaceholderText("Ask about this analysis…")).toHaveValue(REQUEST);
  });

  it("shows that it is reconnecting instead of a button that looks ready", () => {
    agentState.status = "resuming";
    render(<AgentChat analysisId={1} />);

    expect(screen.getByRole("button", { name: "Reconnecting…" })).toBeDisabled();
    expect(screen.getByText("Reconnecting to the agent…")).toBeInTheDocument();
    agentState.status = "ready";
  });
});