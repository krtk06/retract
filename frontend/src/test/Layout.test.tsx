import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, within } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it } from "vitest";
import { Layout } from "../components/Layout";
import type { User } from "../api/types";

const user: User = {
  id: 1,
  login: "krztk2",
  github_id: null,
  email: "k@example.com",
  email_verified: true,
};

function renderLayout(path = "/") {
  // Layout calls useQueryClient for logout and VerifyEmailBanner runs a ["me"]
  // query, so the shell needs the provider it gets in the real app. Retries off so
  // a rejected fetch does not keep the test's timers alive.
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });

  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter initialEntries={[path]}>
        <Layout user={user}>
          <p>content</p>
        </Layout>
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

describe("Layout", () => {
  it("renders a window title bar carrying the wordmark", () => {
    const { container } = renderLayout();
    expect(container.querySelector(".px-titlebar")).not.toBeNull();
    expect(screen.getByText("RETRACT")).toBeInTheDocument();
  });

  it("puts navigation in the sidebar, not the title bar", () => {
    const { container } = renderLayout("/repos");
    const sidebar = container.querySelector<HTMLElement>("nav[aria-label='Primary']")!;
    expect(sidebar).not.toBeNull();
    // Scoped to the sidebar rather than the whole screen: the mobile tab strip is
    // a second <nav aria-label="Primary"> rendering the same two links, so an
    // unscoped query matches twice and asserts nothing about which nav owns it.
    const link = within(sidebar).getByRole("link", { name: /repositories/i });
    expect(sidebar.contains(link)).toBe(true);
    expect(link).toHaveAttribute("aria-current", "page");
  });

  it("keeps a skip link, and it is the first focusable thing", () => {
    renderLayout();
    expect(screen.getByRole("link", { name: /skip to content/i })).toHaveAttribute("href", "#content");
  });

  it("shows the user and a log out control", () => {
    renderLayout();
    // The login appears twice by design — in the title bar beside Log out, and in
    // the sidebar's "signed in" well — so the assertion is on both occurrences.
    expect(screen.getAllByText("krztk2")).toHaveLength(2);
    expect(screen.getByRole("button", { name: /log out/i })).toBeInTheDocument();
  });

  it("marks the window dots decorative", () => {
    const { container } = renderLayout();
    const dots = container.querySelectorAll("[data-window-dot]");
    expect(dots).toHaveLength(3);
    for (const dot of dots) expect(dot.getAttribute("aria-hidden")).toBe("true");
  });
});