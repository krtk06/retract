import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { Meter } from "../components/Meter";

describe("Meter", () => {
  it("draws a track and fills it for a value", () => {
    render(<Meter value={55} label="Testing" />);
    const bar = screen.getByRole("progressbar", { name: "Testing" });
    expect(bar.querySelector('[data-filled="true"]')).not.toBeNull();
    expect(bar.querySelector('[data-unmeasured="true"]')).toBeNull();
  });

  it("hatches the track and drops the value when the number is null", () => {
    const { container } = render(<Meter value={null} label="Dependencies" />);
    expect(container.querySelector('[data-unmeasured="true"]')).not.toBeNull();
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

  it("omits aria-valuenow when the value is unmeasured", () => {
    render(<Meter value={null} label="Dependencies" />);
    expect(screen.getByRole("progressbar", { name: "Dependencies" })).not.toHaveAttribute(
      "aria-valuenow",
    );
  });
});
