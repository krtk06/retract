import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { ICONS, Icon } from "../components/Icon";

describe("Icon", () => {
  it("renders every icon in the set", () => {
    for (const name of Object.keys(ICONS) as Array<keyof typeof ICONS>) {
      const { container, unmount } = render(<Icon name={name} />);
      expect(container.querySelector("svg"), `${name} failed to render`).not.toBeNull();
      unmount();
    }
  });

  it("draws with a currentColor stroke", () => {
    const { container } = render(<Icon name="sun" />);
    const svg = container.querySelector("svg")!;
    expect(svg.getAttribute("stroke")).toBe("currentColor");
    expect(svg.getAttribute("fill")).toBe("none");
  });

  it("is decorative unless given a title", () => {
    const { container, rerender } = render(<Icon name="sun" />);
    expect(container.querySelector("svg")!.getAttribute("aria-hidden")).toBe("true");
    rerender(<Icon name="sun" title="Light theme" />);
    expect(screen.getByTitle("Light theme")).toBeInTheDocument();
  });
});
