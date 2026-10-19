import { render } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { Sparkline } from "../components/Sparkline";

describe("Sparkline", () => {
  it("draws a path when there is a trend", () => {
    const { container } = render(<Sparkline values={[60, 64, 58, 72]} />);
    expect(container.querySelector("path")).not.toBeNull();
    expect(container.querySelector("circle")).not.toBeNull();
  });

  it("renders nothing for fewer than two points", () => {
    const { container } = render(<Sparkline values={[60]} />);
    expect(container).toBeEmptyDOMElement();
  });
});
