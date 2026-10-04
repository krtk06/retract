import { render, screen } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { describe, expect, it, vi } from "vitest";

import { AnalysisDetailPage } from "../pages/AnalysisDetailPage";

// vi.mock factories are hoisted above module-level consts, so the fixture has to be
// hoisted with them.
const { analysis } = vi.hoisted(() => ({
  analysis: {
    id: 1,
    repository: "krtk06/Chaty",
    commit_sha: "175c883872699ee723af18e2c60dcb5a51f385ef",
    status: "done",
    created_at: "2026-10-04T16:25:22Z",
    started_at: "2026-10-04T16:25:22Z",
    finished_at: "2026-10-04T16:25:34Z",
    loc: 2565,
    error: null,
    pending_approvals: 0,
    published: true,
    finding_count: 13,
    score_json: null,
  },
}));

vi.mock("../api/client", () => ({
  api: {
    getAnalysis: vi.fn().mockResolvedValue(analysis),
    getFindings: vi.fn().mockResolvedValue([]),
  },
}));

vi.mock("@tanstack/react-query", async (importOriginal) => {
  const actual = await importOriginal<typeof import("@tanstack/react-query")>();
  return {
    ...actual,
    useQueryClient: () => ({ invalidateQueries: vi.fn() }),
    useQuery: ({ queryKey }: { queryKey: string[] }) => ({
      // ["score", id] is gated on a finished analysis; stub the rest as loaded.
      data: queryKey[0] === "analysis" ? analysis : queryKey[0] === "findings" ? [] : null,
    }),
  };
});

// The page subscribes to the progress SSE stream, which jsdom does not implement.
vi.stubGlobal(
  "EventSource",
  class {
    close() {}
    addEventListener() {}
  },
);

describe("AnalysisDetailPage", () => {
  it("offers a way back to the repository list", () => {
    // The header title also links to "/", but it reads as a static heading, so the
    // page needs its own control. Assert the destination rather than the label:
    // the wording is a presentation choice.
    render(
      <MemoryRouter initialEntries={["/analyses/1"]}>
        <Routes>
          <Route path="/analyses/:id" element={<AnalysisDetailPage />} />
        </Routes>
      </MemoryRouter>,
    );

    const back = screen.getByRole("link", { name: /back/i });
    expect(back).toHaveAttribute("href", "/");
  });
});