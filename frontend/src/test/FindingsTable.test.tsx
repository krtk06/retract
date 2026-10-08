import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { FindingsTable } from "../components/FindingsTable";
import type { Finding } from "../api/types";

const { copyTextMock } = vi.hoisted(() => ({
  // Typed so the recorded calls carry the payload as one string argument,
  // which is what the tests assert through mock.calls. The implementation
  // ignores it; returning true exercises the "Copied ✓" state.
  copyTextMock: vi.fn<(text: string) => Promise<boolean>>(async () => true),
}));

vi.mock("../lib/clipboard", () => ({ copyText: copyTextMock }));

// The row's snippet query only fires when expanded; mocked here so the table
// can render without the API.
vi.mock("../api/hooks", () => ({
  useSnippet: () => ({ data: null, isLoading: false, isError: false }),
}));

const repository = {
  id: 1,
  owner: "krtk06",
  name: "seedy-python-app",
  url: "https://github.com/krtk06/seedy-python-app",
  default_branch: "main",
  created_at: "2026-10-01T00:00:00Z",
  latest_analysis_id: 18,
  latest_analysis_status: "done",
};

function finding(overrides: Partial<Finding>): Finding {
  return {
    id: 42,
    analysis_id: 18,
    agent: "tool:semgrep",
    category: "injection",
    severity: "high",
    title: "SQL query built with an f-string",
    description: "find_user() interpolates the caller-controlled name.",
    file_path: "app/db.py",
    line_start: 8,
    line_end: null,
    evidence_json: null,
    verifier: "verified:source-pattern",
    confidence: 0.9,
    status: "verified",
    created_at: "2026-10-08T00:00:00Z",
    remediation: { action: "Use parameterised queries", effort: "low", source: "catalog" },
    ...overrides,
  };
}

function renderTable(findings: Finding[]) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={client}>
      <FindingsTable findings={findings} repository={repository} commitSha="abc123def456" analysisId={18} />
    </QueryClientProvider>,
  );
}

beforeEach(() => {
  copyTextMock.mockClear();
  copyTextMock.mockImplementation(async () => true);
});

describe("FindingsTable — Fix with your agent", () => {
  it("copies the fix brief and confirms it", async () => {
    renderTable([finding({})]);

    fireEvent.click(screen.getByRole("button", { name: "Fix with your agent" }));

    await waitFor(() => expect(copyTextMock).toHaveBeenCalledTimes(1));
    const text = String(copyTextMock.mock.calls[0][0]);
    expect(text).toContain("# Retract");
    expect(text).toContain("npx skills add krtk06/retract --skill retract");
    expect(text).toContain("Use the retract skill to resolve this finding");
    expect(text).toContain("finding_id: 42");
    expect(screen.getByText("Copied ✓")).toBeInTheDocument();
  });

  it("renders disabled for a dismissed finding and copies nothing", () => {
    renderTable([finding({ status: "dismissed" })]);

    expect(screen.queryByRole("button", { name: "Fix with your agent" })).not.toBeInTheDocument();
    expect(screen.getByText("fix with your agent")).toBeInTheDocument();
    expect(copyTextMock).not.toHaveBeenCalled();
  });

  it("carries the finding's category, severity and citation into the brief", async () => {
    renderTable([finding({ category: "secret", severity: "critical", line_end: null })]);

    fireEvent.click(screen.getByRole("button", { name: "Fix with your agent" }));
    await waitFor(() => expect(copyTextMock).toHaveBeenCalled());

    const text = String(copyTextMock.mock.calls[0][0]);
    expect(text).toContain("category: secret · pillar: security");
    expect(text).toContain("severity: critical");
    expect(text).toContain("Cited location: app/db.py:8");
  });
});
