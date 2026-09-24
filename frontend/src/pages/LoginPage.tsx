import { useState } from "react";
import { useQueryClient } from "@tanstack/react-query";

import { api, ApiError } from "../api/client";

export function LoginPage() {
  const queryClient = useQueryClient();
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function handleDevLogin() {
    setBusy(true);
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
      setBusy(false);
    }
  }

  return (
    <div className="flex min-h-screen items-center justify-center">
      <div className="w-full max-w-sm rounded-xl border border-zinc-800 bg-zinc-900 p-8 shadow-xl">
        <h1 className="mb-2 text-xl font-semibold">AI Engineering Intelligence</h1>
        <p className="mb-6 text-sm text-zinc-400">
          Analyze a GitHub repository for quality, security, testing, and documentation
          health.
        </p>
        {error && (
          <p className="mb-4 rounded-md bg-red-950 px-3 py-2 text-sm text-red-300">{error}</p>
        )}
        <a
          href="/api/auth/github/login"
          className="mb-3 block w-full rounded-md bg-zinc-100 px-4 py-2 text-center text-sm font-medium text-zinc-900 hover:bg-white"
        >
          Sign in with GitHub
        </a>
        <button
          onClick={handleDevLogin}
          disabled={busy}
          className="block w-full rounded-md border border-zinc-700 px-4 py-2 text-sm text-zinc-300 hover:bg-zinc-800 disabled:opacity-50"
        >
          {busy ? "Signing in…" : "Dev login"}
        </button>
      </div>
    </div>
  );
}
