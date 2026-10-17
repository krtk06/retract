import { useEffect, useState } from "react";
import { useQueryClient } from "@tanstack/react-query";

import { api, ApiError } from "../api/client";
import { useLogin, useRegister } from "../api/hooks";
import { PixelIcon } from "../components/PixelIcon";
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
    <div className="relative grid min-h-[100dvh] place-items-center bg-canvas p-6">
      {/* Dithered sky behind the frame — a 2px checkerboard, not a gradient. */}
      <div
        aria-hidden="true"
        className="px-dither pointer-events-none fixed inset-0 opacity-30"
      />

      <div className="absolute right-4 top-4 sm:right-6 sm:top-5">
        <ThemeToggle />
      </div>

      <div className="anim-step-in relative w-full max-w-[30rem]">
        <div className="px-frame">
          <div className="px-titlebar">
            <span className="flex items-center gap-2">
              <PixelIcon name="logo" size={10} className="text-accent" />
              RETRACT.EXE
            </span>
            <span className="ml-auto flex gap-1" aria-hidden="true">
              <span className="block h-[8px] w-[8px] bg-danger" />
              <span className="block h-[8px] w-[8px] bg-warn" />
              <span className="block h-[8px] w-[8px] bg-ok" />
            </span>
          </div>

          <div className="flex flex-col gap-4 p-5">
            <div className="flex items-center gap-4">
              <span aria-hidden="true" className="anim-blink block text-accent">
                <PixelIcon name="robot-open" size={48} />
              </span>
              <div>
                <p className="px-eyebrow">Repository health</p>
                <h1 className="font-ui text-[20px] font-bold tracking-[0.18em] text-ink">
                  RETRACT
                </h1>
              </div>
            </div>

            <div>
              <p className="px-eyebrow mb-1">System health</p>
              <span className="anim-slide-up flex gap-[2px] border-2 border-line bg-canvas p-[2px]">
                {Array.from({ length: 20 }, (_, index) => (
                  <span
                    key={index}
                    className="block h-[8px] w-[8px]"
                    style={{
                      background: index < 13 ? "var(--ok)" : "var(--line-strong)",
                      opacity: index < 13 ? 1 : 0.35,
                    }}
                  />
                ))}
              </span>
            </div>

            <p className="text-[13px] leading-relaxed text-muted">
              Give it a GitHub repository. Get back a health score with verified, cited
              findings.
            </p>

            {emailVerified && !error && (
              <p className="border border-ok/25 bg-ok-soft px-3.5 py-2.5 text-sm text-ok">
                Your email is verified. Sign in — GitHub will now reach the same account.
              </p>
            )}
            {error && (
              <p className="border border-danger/25 bg-danger-soft px-3.5 py-2.5 text-sm text-danger">
                {error}
              </p>
            )}

            <a href="/api/auth/github/login" className="px-btn px-btn--ink w-full">
              <PixelIcon name="github" size={12} />
              Sign in with GitHub
            </a>

            <div className="flex items-center gap-3 text-xs text-faint">
              <span className="px-rule flex-1" />
              or use your email
              <span className="px-rule flex-1" />
            </div>

            <div role="tablist" aria-label="Sign-in method" className="px-tabs grid-cols-2">
              <button
                type="button"
                aria-pressed={mode === "login"}
                onClick={() => {
                  setMode("login");
                  setError(null);
                }}
                className={`px-tab ${mode === "login" ? "px-tab-active" : ""}`}
              >
                Sign in
              </button>
              <button
                type="button"
                aria-pressed={mode === "register"}
                onClick={() => {
                  setMode("register");
                  setError(null);
                }}
                className={`px-tab ${mode === "register" ? "px-tab-active" : ""}`}
              >
                Create account
              </button>
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
                className="px-btn px-btn--ghost mt-4 w-full"
              >
                {devBusy ? "Signing in…" : "Dev login"}
              </button>
            )}
          </div>
        </div>
        <p className="mt-5 text-center font-mono text-[10px] text-faint">
          Your code is cloned and analyzed on this deployment. Nothing is pushed back.
        </p>
      </div>
    </div>
  );
}
