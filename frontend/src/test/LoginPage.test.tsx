import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, within } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { LoginPage } from "../pages/LoginPage";

vi.mock("@tanstack/react-query", async (importOriginal) => {
  const actual = await importOriginal<typeof import("@tanstack/react-query")>();
  return {
    ...actual,
    useQueryClient: () => ({ invalidateQueries: vi.fn() }),
  };
});

function renderLogin() {
  const client = new QueryClient();
  return render(
    <QueryClientProvider client={client}>
      <LoginPage />
    </QueryClientProvider>,
  );
}

describe("LoginPage", () => {
  it("renders sign-in options", () => {
    renderLogin();
    expect(screen.getByText("Sign in with GitHub")).toBeInTheDocument();
    expect(screen.getByText("Dev login")).toBeInTheDocument();
    expect(
      screen.getByRole("link", { name: "Sign in with GitHub" }),
    ).toHaveAttribute("href", "/api/auth/github/login");
    // Email/password lives here too, toggled with register.
    expect(screen.getByPlaceholderText("you@example.com")).toBeInTheDocument();
    const form = within(screen.getByRole("form", { name: "Email sign-in" }));
    expect(form.getByRole("button")).toHaveTextContent("Sign in");
  });

  it("toggles to create an account", () => {
    renderLogin();
    fireEvent.click(screen.getByRole("button", { name: "Create account" }));
    const form = within(screen.getByRole("form", { name: "Email sign-in" }));
    expect(screen.getByPlaceholderText("At least 8 characters")).toBeInTheDocument();
    expect(form.getByRole("button")).toHaveTextContent("Create account");
    // Switching back to sign-in relaxes the password requirement.
    fireEvent.click(screen.getByRole("button", { name: "Sign in" }));
    expect(screen.getByPlaceholderText("Password")).toBeInTheDocument();
  });
});
