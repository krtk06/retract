import { useEffect, useState } from "react";
import { useQueryClient } from "@tanstack/react-query";

import { api, ApiError } from "../api/client";
import { useLogin, useRegister } from "../api/hooks";
import { ThemeToggle } from "../components/ThemeToggle";

type Mode = "login" | "register";

// The backend sends a browser back here with one of these after a failed GitHub
// sign-in, rather than dumping JSON at an API URL. Each says what happened and
// what to do about it, because the alternative — "Invalid OAuth state" at
// /api/auth/github/callback — tells the user nothing they can act on.
const AUTH_ERRORS: Record<string, string> = {
  expired_state:
    "That sign-in attempt expired. Signing in with GitHub can take a couple of minutes — try again.",
  used_state: "That sign-in link was already used. If you are signed in, go back to the dashboard.",
  not_configured: "GitHub sign-in is not configured on this deployment.",
  exchange_failed: "GitHub did not complete the sign-in. Try again.",
  profile_failed: "Could not read your GitHub profile. Try again.",
  verification_failed:
    "That verification link is invalid, used, or expired. Sign in and send yourself a new one.",
};

function authErrorFromUrl(): string | null {
  const code = new URLSearchParams(window.location.search).get("auth_error");
  return AUTH_ERRORS[code ?? ""] ?? (code ? AUTH_FALLBACK : null);
}

/**
 * Whether this load is the landing from a verification link.
 *
 * The link arrives from a mail client, in whatever browser the user reads mail in —
 * often not one with a session. So the outcome is acknowledged here as well as in
 * the app, or a successful verification looks like nothing happened.
 */
function verifiedFromUrl(): boolean {
  return new URLSearchParams(window.location.search).get("email_verified") === "1";
}

const AUTH_FALLBACK = "GitHub sign-in did not complete. Try again.";

function GitHubMark() {
  return (
    <svg viewBox="0 0 24 24" fill="currentColor" className="h-4 w-4" aria-hidden="true">
      <path d="M12 .5C5.73.5.5 5.73.5 12c0 5.08 3.29 9.39 7.86 10.91.58.11.79-.25.79-.56 0-.28-.01-1.02-.02-2-3.2.7-3.88-1.54-3.88-1.54-.52-1.33-1.28-1.68-1.28-1.68-1.05-.72.08-.7.08-.7 1.16.08 1.77 1.19 1.77 1.19 1.03 1.77 2.7 1.26 3.36.96.1-.75.4-1.26.73-1.55-2.56-.29-5.25-1.28-5.25-5.7 0-1.26.45-2.29 1.19-3.1-.12-.29-.52-1.46.11-3.05 0 0 .97-.31 3.18 1.18a11 11 0 0 1 5.8 0c2.2-1.49 3.17-1.18 3.17-1.18.63 1.59.23 2.76.11 3.05.74.81 1.19 1.84 1.19 3.1 0 4.43-2.69 5.41-5.26 5.69.41.36.78 1.06.78 2.14 0 1.55-.01 2.8-.01 3.18 0 .31.21.68.8.56A11.5 11.5 0 0 0 23.5 12C23.5 5.73 18.27.5 12 .5Z" />
    </svg>
  );
}

function ModeTab({
  active,
  onSelect,
  children,
}: {
  active: boolean;
  onSelect: () => void;
  children: React.ReactNode;
}) {
  return (
    <button
      type="button"
      onClick={onSelect}
      className={`px-tab ${active ? "px-tab-active" : ""}`}
    >
      {children}
    </button>
  );
}

function EmailAuthForm({
  mode,
  email,
  password,
  pending,
  onEmailChange,
  onPasswordChange,
  onSubmit,
}: {
  mode: Mode;
  email: string;
  password: string;
  pending: boolean;
  onEmailChange: (value: string) => void;
  onPasswordChange: (value: string) => void;
  onSubmit: (event: React.FormEvent) => void;
}) {
  return (
    <form aria-label="Email sign-in" onSubmit={onSubmit} className="space-y-3">
      <input
        type="email"
        value={email}
        onChange={(event) => onEmailChange(event.target.value)}
        placeholder="you@example.com"
        autoComplete="email"
        className="px-input"
        required
      />
      <input
        type="password"
        value={password}
        onChange={(event) => onPasswordChange(event.target.value)}
        placeholder={mode === "register" ? "At least 8 characters" : "Password"}
        autoComplete={mode === "register" ? "new-password" : "current-password"}
        minLength={mode === "register" ? 8 : undefined}
        className="px-input"
        required
      />
      <button
        type="submit"
        disabled={pending}
        className="px-btn px-btn--primary w-full"
      >
        {pending
          ? mode === "register"
            ? "Creating account…"
            : "Signing in…"
          : mode === "register"
            ? "Create account"
            : "Sign in"}
      </button>
    </form>
  );
}

export function LoginPage() {
  const queryClient = useQueryClient();
  const register = useRegister();
  const login = useLogin();
  const [mode, setMode] = useState<Mode>("login");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [devBusy, setDevBusy] = useState(false);

  // Captured during the first render, before the URL is cleaned: reading it in
  // an effect instead loses the message under StrictMode, which runs effects
  // twice — the second run would find the parameter already stripped and wipe
  // the banner that the first run had just set.
  const [authError] = useState(() => authErrorFromUrl());
  const [emailVerified] = useState(() => verifiedFromUrl());
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (authError || emailVerified) {
      // Drop the parameter once read, so a refresh does not re-show a stale
      // message — the same class of bug as the cached 100 score this app once
      // displayed.
      window.history.replaceState({}, "", window.location.pathname);
    }
    if (authError) setError(authError);
  }, [authError, emailVerified]);

  // Dev login exists so local development skips OAuth entirely. The backend
  // already refuses it when RETRACT_DEV_LOGIN=0; there is no reason to show a
  // button that can only 404 in a production build.
  const showDevLogin = import.meta.env.DEV;

  async function handleDevLogin() {
    setDevBusy(true);
    setError(null);
    try {
      await api.devLogin("dev");
      await queryClient.invalidateQueries({ queryKey: ["me"] });
      window.location.reload();
    } catch (err) {
      if (err instanceof ApiError && err.status === 404) {
        setError("Dev login is disabled on this deployment.");
      } else {
        setError("Login failed. Is the API running?");
      }
      setDevBusy(false);
    }
  }

  async function handleSubmit(event: React.FormEvent) {
    event.preventDefault();
    setError(null);
    try {
      if (mode === "register") {
        await register.mutateAsync({ email: email.trim(), password });
      } else {
        await login.mutateAsync({ email: email.trim(), password });
      }
      window.location.reload();
    } catch (err) {
      if (err instanceof ApiError && err.status === 409) {
        setMode("login");
        setError("That email is already registered — sign in instead.");
        return;
      }
      setError(
        err instanceof ApiError
          ? err.message
          : mode === "register"
            ? "Registration failed. Is the API running?"
            : "Login failed. Is the API running?",
      );
    }
  }

  const pending = register.isPending || login.isPending;

  return (
    <div className="relative grid min-h-[100dvh] place-items-center px-4 py-16">
      <div className="absolute right-4 top-4 sm:right-6 sm:top-5">
        <ThemeToggle />
      </div>

      <div className="anim-step-in w-full max-w-[26rem]">
        <div className="px-frame">
          <div className="px-frame p-7 sm:p-8">
            <div className="mb-6 flex items-center gap-3">
              <span
                aria-hidden="true"
                className="h-9 w-9"
                style={{
                  background:
                    "radial-gradient(circle at 35% 30%, var(--accent-strong), var(--accent))",
                  boxShadow: "0 0 26px var(--accent-glow)",
                }}
              />
              <div>
                <h1 className="text-xl font-extrabold tracking-tight">Retract</h1>
                <p className="px-eyebrow mt-0.5">Repository health</p>
              </div>
            </div>

            <p className="mb-6 text-sm leading-relaxed text-muted text-pretty">
              Analyze a GitHub repository for quality, security, testing, and documentation
              health — then come back, re-check it after changes, and track the score.
            </p>

            {emailVerified && !error && (
              <p className="mb-4 border border-ok/25 bg-ok-soft px-3.5 py-2.5 text-sm text-ok">
                Your email is verified. Sign in — GitHub will now reach the same account.
              </p>
            )}
            {error && (
              <p className="mb-4 border border-danger/25 bg-danger-soft px-3.5 py-2.5 text-sm text-danger">
                {error}
              </p>
            )}

            <a
              href="/api/auth/github/login"
              className="px-btn px-btn--ink mb-4 w-full gap-2"
            >
              <GitHubMark />
              Sign in with GitHub
            </a>

            <div className="mb-4 flex items-center gap-3 text-xs text-faint">
              <span className="h-px flex-1 bg-line" />
              or use your email
              <span className="h-px flex-1 bg-line" />
            </div>

            <div className="px-tabs mb-3 grid-cols-2">
              <ModeTab
                active={mode === "login"}
                onSelect={() => {
                  setMode("login");
                  setError(null);
                }}
              >
                Sign in
              </ModeTab>
              <ModeTab
                active={mode === "register"}
                onSelect={() => {
                  setMode("register");
                  setError(null);
                }}
              >
                Create account
              </ModeTab>
            </div>

            <EmailAuthForm
              mode={mode}
              email={email}
              password={password}
              pending={pending}
              onEmailChange={setEmail}
              onPasswordChange={setPassword}
              onSubmit={handleSubmit}
            />

            {showDevLogin && (
              <button
                onClick={handleDevLogin}
                disabled={devBusy}
                className="px-btn px-btn--ghost mt-4 w-full text-muted"
              >
                {devBusy ? "Signing in…" : "Dev login"}
              </button>
            )}
          </div>
        </div>
        <p className="mt-5 text-center text-xs text-faint">
          Your code is cloned and analyzed on this deployment. Nothing is pushed back.
        </p>
      </div>
    </div>
  );
}
