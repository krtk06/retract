import { useEffect, useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { m, useReducedMotion } from "motion/react";

import { api, ApiError } from "../api/client";
import { useLogin, useRegister } from "../api/hooks";
import { EASE } from "../lib/motion";
import { Icon } from "../components/Icon";
import { ThemeToggle } from "../components/ThemeToggle";

type Mode = "login" | "register";

/** A headline line that rises out of its own mask, once. */
function MaskLine({ children, delay = 0 }: { children: React.ReactNode; delay?: number }) {
  const reduced = useReducedMotion();
  return (
    <span className="block overflow-hidden">
      <m.span
        className="block"
        initial={{ y: reduced ? 0 : "105%", opacity: reduced ? 0 : 1 }}
        animate={{ y: 0, opacity: 1 }}
        transition={{ duration: 0.65, ease: EASE, delay: reduced ? 0 : delay }}
      >
        {children}
      </m.span>
    </span>
  );
}

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
        className="input"
        required
      />
      <input
        type="password"
        value={password}
        onChange={(event) => onPasswordChange(event.target.value)}
        placeholder={mode === "register" ? "At least 8 characters" : "Password"}
        autoComplete={mode === "register" ? "new-password" : "current-password"}
        minLength={mode === "register" ? 8 : undefined}
        className="input"
        required
      />
      <button type="submit" disabled={pending} className="btn btn--primary w-full">
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


/**
 * The login masthead: what the report is, and one synthetic exhibit so the
 * first viewport shows the product doing its job. The exhibit is labelled as a
 * sample — demonstration data is labelled, never passed off as a claim. The
 * headline lines rise out of their masks once; everything else settles in
 * behind them.
 */
function LoginMasthead() {
  return (
    <div className="hidden lg:block">
      <h1 className="font-display text-5xl leading-[1.1] font-semibold tracking-tight text-ink">
        <MaskLine>Repository health,</MaskLine>
        <MaskLine delay={0.09}>computed not vibes.</MaskLine>
      </h1>
      <m.p
        className="mt-5 max-w-md text-[15px] leading-relaxed text-muted"
        initial={{ opacity: 0, y: 6 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.5, ease: EASE, delay: 0.24 }}
      >
        Point it at a GitHub repository. Get back a health score with verified, cited
        findings — every claim traced to file and line, nothing pushed back.
      </m.p>

      <m.figure
        className="panel mt-8 max-w-md p-5"
        aria-label="A sample report"
        initial={{ opacity: 0, y: 10 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.5, ease: EASE, delay: 0.32 }}
      >
        <figcaption className="label flex items-center justify-between">
          A sample report
          <span className="stamp stamp--soft text-faint">sample</span>
        </figcaption>
        <div className="mt-4 flex items-end justify-between gap-4 border-b border-line pb-4">
          <span className="figure text-4xl text-ink">
            72<span className="font-sans text-base font-normal text-faint">/100</span>
          </span>
          <span className="font-mono text-[11px] text-faint">
            6 pillars · 3 analyzers · 41s
          </span>
        </div>
        <ul className="mt-4 space-y-2.5 text-[12px]">
          <m.li
            className="flex items-center justify-between gap-3"
            initial={{ opacity: 0, x: -4 }}
            animate={{ opacity: 1, x: 0 }}
            transition={{ duration: 0.4, ease: EASE, delay: 0.5 }}
          >
            <span className="truncate text-muted">Hardcoded credential</span>
            <span className="stamp text-warn shrink-0">
              <Icon name="clock" size={10} />
              unverified
            </span>
          </m.li>
          <m.li
            className="flex items-center justify-between gap-3"
            initial={{ opacity: 0, x: -4 }}
            animate={{ opacity: 1, x: 0 }}
            transition={{ duration: 0.4, ease: EASE, delay: 0.6 }}
          >
            <span className="truncate text-muted">SQL query built with an f-string</span>
            <span className="stamp text-ok shrink-0">
              <Icon name="check" size={10} />
              verified
            </span>
          </m.li>
        </ul>
        <p className="mt-4 border-t border-line pt-3 font-mono text-[10px] text-faint">
          app/db.py:8-12 · app/cache_key.py:11
        </p>
      </m.figure>
    </div>
  );
}

function SignInPlate({
  mode,
  onMode,
  email,
  password,
  pending,
  onEmailChange,
  onPasswordChange,
  onSubmit,
  error,
  emailVerified,
  showDevLogin,
  devBusy,
  onDevLogin,
}: {
  mode: Mode;
  onMode: (mode: Mode) => void;
  email: string;
  password: string;
  pending: boolean;
  onEmailChange: (value: string) => void;
  onPasswordChange: (value: string) => void;
  onSubmit: (event: React.FormEvent) => void;
  error: string | null;
  emailVerified: boolean;
  showDevLogin: boolean;
  devBusy: boolean;
  onDevLogin: () => void;
}) {
  return (
    <m.div
      className="frame p-7"
      initial={{ opacity: 0, y: 12 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.55, ease: EASE, delay: 0.16 }}
    >
      <div className="flex items-center gap-3">
        <span className="grid h-10 w-10 place-items-center rounded-[2px] bg-accent-soft text-ink">
          <Icon name="logo" size={22} />
        </span>
        <div>
          <h2 className="font-display text-lg font-semibold tracking-tight text-ink">
            Retract
          </h2>
        </div>
      </div>

      <p className="mt-5 text-[13px] leading-relaxed text-muted lg:hidden">
        Give it a GitHub repository. Get back a health score with verified, cited findings.
      </p>

      {emailVerified && !error && (
        <p className="mt-4 flex items-center gap-2 rounded-[2px] border border-ok/40 bg-ok-soft px-3.5 py-2.5 text-[13px] text-ok">
          <Icon name="check" size={15} />
          Your email is verified. Sign in — GitHub will now reach the same account.
        </p>
      )}
      {error && (
        <p className="mt-4 rounded-[2px] border border-danger/40 bg-danger-soft px-3.5 py-2.5 text-[13px] text-danger">
          {error}
        </p>
      )}

      <a href="/api/auth/github/login" className="btn btn--primary sheen press mt-5 w-full">
        <Icon name="github" size={16} />
        Sign in with GitHub
      </a>

      <div className="my-5 flex items-center gap-3 text-[11px] text-faint">
        <span className="rule flex-1" />
        or use your email
        <span className="rule flex-1" />
      </div>

      {/* A pressed-button group, not a tablist: a tablist requires `tab`
          children, and these must stay `button` so the accessible names
          "Sign in" / "Create account" keep resolving as buttons. A
          tablist wrapping non-tabs is invalid ARIA. */}
      <div role="group" aria-label="Sign-in method" className="tabs mb-4">
        <button
          type="button"
          aria-pressed={mode === "login"}
          onClick={() => onMode("login")}
          className={`tab ${mode === "login" ? "tab-active" : ""}`}
        >
          Sign in
        </button>
        <button
          type="button"
          aria-pressed={mode === "register"}
          onClick={() => onMode("register")}
          className={`tab ${mode === "register" ? "tab-active" : ""}`}
        >
          Create account
        </button>
      </div>

      <EmailAuthForm
        mode={mode}
        email={email}
        password={password}
        pending={pending}
        onEmailChange={onEmailChange}
        onPasswordChange={onPasswordChange}
        onSubmit={onSubmit}
      />

      {showDevLogin && (
        <button
          onClick={onDevLogin}
          disabled={devBusy}
          className="btn btn--ghost mt-4 w-full"
        >
          {devBusy ? "Signing in…" : "Dev login"}
        </button>
      )}
    </m.div>
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
    <div className="paper relative grid min-h-[100dvh] place-items-center bg-canvas p-6">
      <div className="absolute right-4 top-4 sm:right-6 sm:top-5">
        <ThemeToggle />
      </div>

      <div className="mx-auto grid w-full max-w-5xl items-center gap-10 lg:grid-cols-[1fr_26rem] lg:gap-14">
        <LoginMasthead />

        <div className="w-full justify-self-center max-w-[26rem] lg:justify-self-end">
          <SignInPlate
            mode={mode}
            onMode={(next) => {
              setMode(next);
              setError(null);
            }}
            email={email}
            password={password}
            pending={pending}
            onEmailChange={setEmail}
            onPasswordChange={setPassword}
            onSubmit={handleSubmit}
            error={error}
            emailVerified={emailVerified}
            showDevLogin={showDevLogin}
            devBusy={devBusy}
            onDevLogin={handleDevLogin}
          />
          <p className="mt-5 text-center font-mono text-[11px] text-faint">
            Your code is cloned and analyzed on this deployment. Nothing is pushed back.
          </p>
        </div>
      </div>
    </div>
  );
}
