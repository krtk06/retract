import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it } from "vitest";
import { EmptyState, Loading } from "../components/EmptyState";

describe("EmptyState", () => {
  it("shows a title and an optional detail", () => {
    render(<EmptyState title="No analyses yet" detail="Point it at a repository." />);
    expect(screen.getByText("No analyses yet")).toBeInTheDocument();
    expect(screen.getByText("Point it at a repository.")).toBeInTheDocument();
  });

  it("renders an action link", () => {
    render(
      <MemoryRouter>
        <EmptyState title="Nothing" action={{ label: "Add a repo", to: "/repos" }} />
      </MemoryRouter>,
    );
    expect(screen.getByRole("link", { name: "Add a repo" })).toHaveAttribute("href", "/repos");
  });
});

describe("Loading", () => {
  it("announces the label and draws the requested number of rows", () => {
    const { container } = render(<Loading label="Loading graph…" rows={4} />);
    expect(screen.getByText("Loading graph…")).toBeInTheDocument();
    expect(container.querySelectorAll(".px-dither")).toHaveLength(4);
  });
});
