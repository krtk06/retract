import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { ScoreHero } from "../components/ScoreHero";
import type { Score } from "../api/types";

/** `ScorePillar.score` is always a number. "Not measured" is `findings === 0`,
 *  which is why an absent-looking pillar here is not modelled by a null score. */
const score: Score = {
  version: 3,
  overall: 64,
  loc: 2565,
  kloc: 2.565,
  basis: "density",
  pillars: {
    security: { score: 42, findings: 13, verified: 12, hypotheses: 1 },
    "code-quality": { score: 88, findings: 5, verified: 5, hypotheses: 0 },
    // findings: 0 — nothing triggered this analyzer, so no score is claimed.
    testing: { score: 100, findings: 0, verified: 0, hypotheses: 0 },
    architecture: { score: 61, findings: 3, verified: 2, hypotheses: 1, dismissed: 1 },
    documentation: { score: 90, findings: 2, verified: 2, hypotheses: 0 },
    dependencies: { score: 75, findings: 4, verified: 4, hypotheses: 0 },
  },
};

describe("ScoreHero", () => {
  it("renders one meter per pillar, all six", () => {
    render(<ScoreHero score={score} />);
    for (const label of [
      "Security",
      "Code quality",
      "Testing",
      "Architecture",
      "Documentation",
      "Dependencies",
    ]) {
      expect(screen.getByRole("progressbar", { name: label })).toBeInTheDocument();
    }
  });

  it("claims no score for a pillar with zero findings", () => {
    render(<ScoreHero score={score} />);
    const testing = screen.getByRole("progressbar", { name: "Testing" });
    // aria-valuenow is omitted rather than set to the backend's flattering 100.
    expect(testing).not.toHaveAttribute("aria-valuenow");
    expect(screen.getByText("not measured")).toBeInTheDocument();
  });

  it("keeps the existing count-basis warning verbatim", () => {
    render(<ScoreHero score={{ ...score, basis: "count" }} />);
    expect(
      screen.getByText("No LOC measured — scored on finding count"),
    ).toBeInTheDocument();
  });

  it("returns nothing without a score", () => {
    const { container } = render(<ScoreHero score={null} />);
    expect(container).toBeEmptyDOMElement();
  });
});
