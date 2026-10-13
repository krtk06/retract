import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import type { User } from "../api/types";

const useMe = vi.fn();
const resend = { mutateAsync: vi.fn(), isPending: false };

vi.mock("../api/hooks", () => ({
  useMe: () => useMe(),
  useResendVerification: () => resend,
}));

const { VerifyEmailBanner } = await import("../components/VerifyEmailBanner");

function renderBanner() {
  return render(
    <QueryClientProvider client={new QueryClient()}>
      <VerifyEmailBanner />
    </QueryClientProvider>,
  );
}

function user(overrides: Partial<User> = {}): User {
  return { id: 1, login: "someone", github_id: null, email: "someone@example.com", ...overrides };
}

afterEach(() => {
  window.history.replaceState({}, "", "/");
  vi.clearAllMocks();
});

describe("VerifyEmailBanner", () => {
  it("prompts an unverified account", () => {
    useMe.mockReturnValue({ data: user({ email_verified: false }) });
    renderBanner();
    expect(screen.getByText(/Verify/)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Resend email" })).toBeInTheDocument();
  });

  it("stays out of the way once the address is verified", () => {
    useMe.mockReturnValue({ data: user({ email_verified: true }) });
    renderBanner();
    expect(screen.queryByRole("button", { name: "Resend email" })).not.toBeInTheDocument();
  });

  it("says nothing for a GitHub-only account with no address", () => {
    useMe.mockReturnValue({ data: user({ email: null }) });
    renderBanner();
    expect(screen.queryByRole("button", { name: "Resend email" })).not.toBeInTheDocument();
  });

  it("confirms the just-verified landing", () => {
    // The API redirects here after following the emailed link.
    window.history.replaceState({}, "", "/?email_verified=1");
    useMe.mockReturnValue({ data: user({ email_verified: true }) });
    renderBanner();
    expect(screen.getByText(/Email verified/)).toBeInTheDocument();
  });

  it("reports that another link was sent", async () => {
    useMe.mockReturnValue({ data: user({ email_verified: false }) });
    resend.mutateAsync.mockResolvedValue({ ok: true, already_verified: false });
    renderBanner();
    fireEvent.click(screen.getByRole("button", { name: "Resend email" }));
    await waitFor(() => expect(screen.getByText(/Verification email sent/)).toBeInTheDocument());
  });
});
