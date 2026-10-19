import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, within } from "@testing-library/react";
import { StrictMode } from "react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { LoginPage } from "../pages/LoginPage";
import { ThemeProvider } from "../components/ThemeProvider";

vi.mock("@tanstack/react-query", async (importOriginal) => {
  const actual = await importOriginal<typeof import("@tanstack/react-query")>();
  return {
    ...actual,
    useQueryClient: () => ({ invalidateQueries: vi.fn() }),
  };
});

function withSearch(search: string) {
  window.history.replaceState({}, "", `/${search}`);
}

afterEach(() => {
  window.history.replaceState({}, "", "/");
});

function renderLogin() {
  const client = new QueryClient();
  return render(
    <ThemeProvider>
      <QueryClientProvider client={client}>
        <LoginPage />
      </QueryClientProvider>
    </ThemeProvider>,
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

  it("explains a failed GitHub sign-in instead of showing JSON", () => {
    withSearch("?auth_error=expired_state");
    renderLogin();
    expect(screen.getByText(/That sign-in attempt expired/)).toBeInTheDocument();
    // Cleared on read, so a refresh does not re-show a stale failure.
    expect(window.location.search).toBe("");
  });

  it("shows a generic message for an unknown code", () => {
    withSearch("?auth_error=something_new");
    renderLogin();
    expect(screen.getByText(/GitHub sign-in did not complete/)).toBeInTheDocument();
  });

  it("shows no banner on a clean load", () => {
    renderLogin();
    expect(screen.queryByText(/expired/)).not.toBeInTheDocument();
  });

  it("acknowledges a completed email verification", () => {
    // The link is followed from a mail client, in whatever browser the user reads
    // mail in — often one without a session, so this is where they land. Silence
    // here would make a successful verification look like it did nothing.
    withSearch("?email_verified=1");
    renderLogin();
    expect(screen.getByText(/Your email is verified/)).toBeInTheDocument();
    expect(window.location.search).toBe("");
  });

  it("keeps the message under StrictMode double-effects", () => {
    // The browser caught this: an effect that read the parameter and then
    // stripped it lost the message on StrictMode's second run, because the
    // parameter was already gone. Capture-then-clean is the fix; this pins it.
    withSearch("?auth_error=expired_state");
    render(
      <StrictMode>
        <ThemeProvider>
          <QueryClientProvider client={new QueryClient()}>
            <LoginPage />
          </QueryClientProvider>
        </ThemeProvider>
      </StrictMode>,
    );
    expect(screen.getByText(/That sign-in attempt expired/)).toBeInTheDocument();
    expect(window.location.search).toBe("");
  });
});

