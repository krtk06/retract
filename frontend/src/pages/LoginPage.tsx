import { useEffect, useState } from "react";
import { useQueryClient } from "@tanstack/react-query";

import { api, ApiError } from "../api/client";
import { useLogin, useRegister } from "../api/hooks";

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
};

function authErrorFromUrl(): string | null {
  const code = new URLSearchParams(window.location.search).get("auth_error");
  return AUTH_ERRORS[code ?? ""] ?? (code ? AUTH_FALLBACK : null);
}

const AUTH_FALLBACK = "GitHub sign-in did not complete. Try again.";

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
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (authError) {
      // Drop the parameter once read, so a refresh does not re-show a stale
      // error — the same class of bug as the cached 100 score this app once
      // displayed.
      window.history.replaceState({}, "", window.location.pathname);
      setError(authError);
    }
  }, [authError]);

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
    <div className="flex min-h-screen items-center justify-center">
      <div className="w-full max-w-sm rounded-xl border border-zinc-800 bg-zinc-900 p-8 shadow-xl">
        <h1 className="mb-2 text-xl font-semibold">Retract</h1>
        <p className="mb-6 text-sm text-zinc-400">
          Analyze a GitHub repository for quality, security, testing, and documentation
          health — then come back, re-check it after changes, and track the score.
        </p>
        {error && (
          <p className="mb-4 rounded-md bg-red-950 px-3 py-2 text-sm text-red-300">{error}</p>
        )}
        <a
          href="/api/auth/github/login"
          className="mb-4 flex w-full items-center justify-center gap-2 rounded-md bg-zinc-100 px-4 py-2 text-center text-sm font-medium text-zinc-900 hover:bg-white"
        >
          Sign in with GitHub
        </a>

        <div className="mb-4 flex items-center gap-3 text-xs text-zinc-500">
          <span className="h-px flex-1 bg-zinc-800" />
          or use your email
          <span className="h-px flex-1 bg-zinc-800" />
        </div>

        <div className="mb-3 grid grid-cols-2 rounded-md border border-zinc-700 p-1 text-sm">
          <button
            type="button"
            onClick={() => {
              setMode("login");
              setError(null);
            }}
            className={`rounded px-3 py-1 ${
              mode === "login" ? "bg-zinc-800 text-zinc-100" : "text-zinc-400 hover:text-zinc-200"
            }`}
          >
            Sign in
          </button>
          <button
            type="button"
            onClick={() => {
              setMode("register");
              setError(null);
            }}
            className={`rounded px-3 py-1 ${
              mode === "register" ? "bg-zinc-800 text-zinc-100" : "text-zinc-400 hover:text-zinc-200"
            }`}
          >
            Create account
          </button>
        </div>

        <form aria-label="Email sign-in" onSubmit={handleSubmit} className="space-y-3">
          <input
            type="email"
            value={email}
            onChange={(event) => setEmail(event.target.value)}
            placeholder="you@example.com"
            autoComplete="email"
            className="block w-full rounded-md border border-zinc-700 bg-zinc-950 px-3 py-2 text-sm outline-none placeholder:text-zinc-500 focus:border-zinc-500"
            required
          />
          <input
            type="password"
            value={password}
            onChange={(event) => setPassword(event.target.value)}
            placeholder={mode === "register" ? "At least 8 characters" : "Password"}
            autoComplete={mode === "register" ? "new-password" : "current-password"}
            minLength={mode === "register" ? 8 : undefined}
            className="block w-full rounded-md border border-zinc-700 bg-zinc-950 px-3 py-2 text-sm outline-none placeholder:text-zinc-500 focus:border-zinc-500"
            required
          />
          <button
            type="submit"
            disabled={pending}
            className="block w-full rounded-md bg-emerald-600 px-4 py-2 text-sm font-medium text-white hover:bg-emerald-500 disabled:opacity-50"
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

        {showDevLogin && (
          <button
            onClick={handleDevLogin}
            disabled={devBusy}
            className="mt-4 block w-full rounded-md border border-zinc-700 px-4 py-2 text-sm text-zinc-500 hover:bg-zinc-800 disabled:opacity-50"
          >
            {devBusy ? "Signing in…" : "Dev login"}
          </button>
        )}
      </div>
    </div>
  );
}
