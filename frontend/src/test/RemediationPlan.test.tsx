import { fireEvent, render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { RemediationPlanPanel, RemediationSummaryCard } from "../components/RemediationPlan";
import type { RemediationPlan } from "../api/types";

// Mutable so a test can swap in an empty plan: the module-level useQuery mock is
// registered before any test body runs, so vi.doMock could not replace it here.
const { state } = vi.hoisted(() => ({
  state: { plan: null as unknown },
}));

const { plan } = vi.hoisted(() => ({
  plan: {
    analysis_id: 7,
    loc: 2565,
    current_overall: 58,
    projected_overall: 92,
    recoverable_points: 34,
    findings_considered: 13,
    unverified_items: 0,
    truncated_findings: 0,
    work_items: [
      {
        key: "secret",
        pillar: "security",
        action: "Rotate the exposed credential",
        severity: "critical",
        effort: "low",
        source: "catalog",
        steps: ["Revoke and reissue at the provider.", "Move the value into the environment."],
        verify: "Re-run the analysis: the secret finding should disappear.",
        references: ["https://owasp.org/"],
        findings: [
          {
            finding_id: 1,
            title: "Hardcoded secret",
            severity: "critical",
            status: "verified",
            file_path: "app/cache_key.py",
            line_start: 11,
          },
        ],
        finding_count: 1,
        pillar_points: 12,
        weighted_penalty_removed: 30,
        payoff: 30,
      },
      {
        key: "import-cycle",
        pillar: "architecture",
        action: "Break the import cycle",
        severity: "medium",
        effort: "high",
        source: "llm:eve",
        steps: ["Move the shared type into its own module."],
        verify: "Re-run the analysis: the import-cycle finding should disappear.",
        references: [],
        findings: [
          {
            finding_id: 2,
            title: "Import cycle: app.a → app.b",
            severity: "medium",
            status: "hypothesis",
            file_path: "app/a.py",
            line_start: 1,
          },
        ],
        finding_count: 1,
        pillar_points: 4,
        weighted_penalty_removed: 10,
        payoff: 1.25,
      },
    ],
  } as RemediationPlan,
}));

beforeEach(() => {
  state.plan = plan;
});

vi.mock("@tanstack/react-query", async (importOriginal) => {
  const actual = await importOriginal<typeof import("@tanstack/react-query")>();
  return {
    ...actual,
    useQuery: ({ queryKey }: { queryKey: string[] }) => ({
      data: queryKey[0] === "remediation" ? state.plan : null,
      isLoading: false,
      isError: false,
    }),
  };
});

const repository = {
  id: 1,
  owner: "krtk06",
  name: "Chaty",
  url: "https://github.com/krtk06/Chaty",
  default_branch: "main",
  created_at: "2026-10-04T00:00:00Z",
  latest_analysis_id: 7,
  latest_analysis_status: "done",
};

describe("RemediationPlanPanel", () => {
  it("states the exact before and after, not an estimate", () => {
    render(<RemediationPlanPanel analysisId={7} repository={repository} commitSha="abc123def456" />);

    expect(screen.getByText("58")).toBeInTheDocument();
    expect(screen.getByText("92")).toBeInTheDocument();
    expect(screen.getByText(/if every item below is fixed/)).toBeInTheDocument();
    expect(screen.getByText(/2 work items · 13 findings/)).toBeInTheDocument();
  });

  it("says the per-item points are a pillar gain, not a share of the headline", () => {
    render(<RemediationPlanPanel analysisId={7} repository={repository} commitSha="abc123def456" />);

    // Without this the reader would sum the cards and get a number that is wrong:
    // the overall is capped at worst_pillar + 15.
    expect(screen.getByText(/in that item’s own pillar/)).toBeInTheDocument();
    expect(screen.getByText(/Use the order, not a sum/)).toBeInTheDocument();
  });

  it("reveals the steps for a work item on request", () => {
    render(<RemediationPlanPanel analysisId={7} repository={repository} commitSha="abc123def456" />);

    expect(screen.queryByText("Revoke and reissue at the provider.")).not.toBeInTheDocument();
    fireEvent.click(screen.getAllByRole("button", { name: /show the steps/ })[0]);

    expect(screen.getByText("Revoke and reissue at the provider.")).toBeInTheDocument();
    expect(
      screen.getByText(/the secret finding should disappear/),
    ).toBeInTheDocument();
  });

  it("names its references instead of captioning every link 'reference'", () => {
    render(<RemediationPlanPanel analysisId={7} repository={repository} commitSha="abc123def456" />);

    fireEvent.click(screen.getAllByRole("button", { name: /show the steps/ })[0]);

    const link = screen.getByRole("link", { name: /OWASP/ });
    expect(link).toHaveAttribute("href", "https://owasp.org/");
  });

  it("marks agent-authored advice so it can be told apart from catalog advice", () => {
    render(<RemediationPlanPanel analysisId={7} repository={repository} commitSha="abc123def456" />);
    expect(screen.getByText("agent-authored")).toBeInTheDocument();
  });

  it("keeps two work items of the same category independently expandable", () => {
    // Two vulnerable dependencies share the `vulnerable-dependency` key. Keying on
    // the category made React reuse one element for both, so the expand control on
    // the second card silently did nothing.
    state.plan = {
      ...plan,
      work_items: [
        { ...plan.work_items[0], key: "vulnerable-dependency", action: "Upgrade flask" },
        { ...plan.work_items[1], key: "vulnerable-dependency", action: "Upgrade requests" },
      ],
    };
    render(<RemediationPlanPanel analysisId={7} repository={repository} commitSha="abc123def456" />);

    const toggles = screen.getAllByRole("button", { name: /show the steps/ });
    expect(toggles).toHaveLength(2);
    fireEvent.click(toggles[1]);

    // The second card's own steps appear, not the first card's.
    expect(screen.getByText("Move the shared type into its own module.")).toBeInTheDocument();
    expect(screen.queryByText("Revoke and reissue at the provider.")).not.toBeInTheDocument();
  });

  it("offers the plan as a downloadable document", () => {
    render(<RemediationPlanPanel analysisId={7} repository={repository} commitSha="abc123def456" />);
    const link = screen.getByRole("link", { name: /Download \.md/ });
    expect(link).toHaveAttribute("href", "/api/analyses/7/remediation.md");
    expect(link).toHaveAttribute("download");
  });

  it("links an affected finding back to its line on GitHub", () => {
    render(<RemediationPlanPanel analysisId={7} repository={repository} commitSha="abc123def456" />);

    fireEvent.click(screen.getAllByRole("button", { name: /show the steps/ })[0]);
    fireEvent.click(screen.getByRole("button", { name: /show 1 findings/ }));

    expect(screen.getByRole("link", { name: /on GitHub/ })).toHaveAttribute(
      "href",
      "https://github.com/krtk06/Chaty/blob/abc123def456/app/cache_key.py#L11",
    );
  });

  it("says so plainly when there is nothing to fix", () => {
    // A clean repository must get an explicit empty state, not an empty list that
    // reads as "still loading" or, worse, as a plan with nothing in it.
    state.plan = {
      ...plan,
      work_items: [],
      findings_considered: 0,
      projected_overall: null,
      recoverable_points: null,
    };
    render(<RemediationPlanPanel analysisId={7} repository={repository} commitSha="abc123def456" />);

    expect(
      screen.getByText(/Nothing to fix\. No open findings were recorded/),
    ).toBeInTheDocument();
    expect(screen.queryByText("Rotate the exposed credential")).not.toBeInTheDocument();
  });

  it("hides the overview summary card when there is nothing to fix", () => {
    state.plan = { ...plan, work_items: [], findings_considered: 0 };
    const { container } = render(<RemediationSummaryCard analysisId={7} onOpen={vi.fn()} />);
    expect(container).toBeEmptyDOMElement();
  });
});

describe("RemediationSummaryCard", () => {
  it("closes the overview with the headline and the cheapest next step", () => {
    const onOpen = vi.fn();
    render(<RemediationSummaryCard analysisId={7} onOpen={onOpen} />);

    expect(screen.getByText("How to fix these issues")).toBeInTheDocument();
    expect(screen.getByText("58 → 92")).toBeInTheDocument();
    expect(screen.getByText("Rotate the exposed credential")).toBeInTheDocument();
  });

  it("hands off to the full plan when opened", () => {
    const onOpen = vi.fn();
    render(<RemediationSummaryCard analysisId={7} onOpen={onOpen} />);

    fireEvent.click(screen.getByRole("button", { name: /Open fix plan/ }));
    expect(onOpen).toHaveBeenCalledOnce();
  });
});
