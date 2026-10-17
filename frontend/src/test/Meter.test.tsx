import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { METER_CELLS, Meter, ScoreRing } from "../components/Meter";

describe("Meter", () => {
  it("renders exactly 20 cells", () => {
    render(<Meter value={55} label="Testing" />);
    expect(screen.getByRole("progressbar").querySelectorAll("[data-lit]")).toHaveLength(
      METER_CELLS,
    );
  });

  it("fills 11 of 20 cells at 55", () => {
    render(<Meter value={55} label="Testing" />);
    const lit = screen
      .getByRole("progressbar")
      .querySelectorAll('[data-lit="true"]');
    expect(lit).toHaveLength(11);
  });

  it("dithers and drops the value when the number is null", () => {
    const { container } = render(<Meter value={null} label="Dependencies" />);
    expect(container.querySelector(".px-dither")).not.toBeNull();
    // "not measured" must not read as a score, and must not read as zero either.
    expect(screen.queryByText("0")).toBeNull();
    expect(screen.getByText("—")).toBeInTheDocument();
  });

  it("carries the label and value to assistive tech", () => {
    render(<Meter value={72} label="Security" />);
    const bar = screen.getByRole("progressbar", { name: "Security" });
    expect(bar).toHaveAttribute("aria-valuenow", "72");
    expect(bar).toHaveAttribute("aria-valuemin", "0");
    expect(bar).toHaveAttribute("aria-valuemax", "100");
  });
});

describe("ScoreRing", () => {
  it("lights 20% of the ring for a score of 20", () => {
    const { container } = render(<ScoreRing value={20} tone="ok" theme="dark" />);
    expect(container.querySelectorAll('[data-lit="true"]')).toHaveLength(4);
  });

  it("lights every cell at 100", () => {
    const { container } = render(<ScoreRing value={100} tone="ok" theme="dark" />);
    expect(container.querySelectorAll('[data-lit="true"]')).toHaveLength(METER_CELLS);
  });

  it("paints with a literal hex, since a CSS variable cannot be read back", () => {
    const { container } = render(<ScoreRing value={60} tone="ok" theme="dark" />);
    expect(container.innerHTML).toContain("#00E436");
  });
});
