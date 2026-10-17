import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { ICONS, PixelIcon } from "../components/PixelIcon";

describe("PixelIcon", () => {
  it("has only rectangular, binary grids", () => {
    for (const [name, grid] of Object.entries(ICONS)) {
      const width = grid[0].length;
      expect(grid.length, `${name} must have at least one row`).toBeGreaterThan(0);
      for (const row of grid) {
        expect(row.length, `${name} row is not ${width} wide`).toBe(width);
        expect(/^[.#o]+$/.test(row), `${name} row "${row}" is not binary`).toBe(true);
      }
    }
  });

  it("renders one rect per lit cell", () => {
    const { container } = render(<PixelIcon name="chevron-down" />);
    const lit = ICONS["chevron-down"].join("").split("").filter((c) => c === "#").length;
    expect(container.querySelectorAll("rect")).toHaveLength(lit);
  });

  it("paints crisp edges and inherits colour", () => {
    const { container } = render(<PixelIcon name="sun" />);
    const svg = container.querySelector("svg")!;
    expect(svg.getAttribute("shape-rendering")).toBe("crispEdges");
    expect(svg.getAttribute("fill")).toBe("currentColor");
  });

  it("is decorative unless given a title", () => {
    const { container, rerender } = render(<PixelIcon name="sun" />);
    expect(container.querySelector("svg")!.getAttribute("aria-hidden")).toBe("true");
    rerender(<PixelIcon name="sun" title="Light theme" />);
    expect(screen.getByTitle("Light theme")).toBeInTheDocument();
  });
});