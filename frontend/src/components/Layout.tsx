import { useQueryClient } from "@tanstack/react-query";
import type { ReactNode } from "react";
import { Link } from "react-router-dom";

import { api } from "../api/client";
import type { User } from "../api/types";

export function Layout({ user, children }: { user: User; children: ReactNode }) {
  const queryClient = useQueryClient();

  async function handleLogout() {
    await api.logout();
    await queryClient.invalidateQueries({ queryKey: ["me"] });
    window.location.reload();
  }

  return (
    <div className="min-h-screen">
      <header className="border-b border-zinc-800 bg-zinc-900/60">
        <div className="mx-auto flex max-w-5xl items-center justify-between px-6 py-4">
          {/* This is the only way back to the repository list from an analysis, so it
              has to look like a link. It was plain text with no hover cue, which read
              as a static heading — verified working but undiscoverable. */}
          <Link
            to="/"
            className="text-lg font-semibold tracking-tight text-zinc-300 hover:text-white hover:underline"
          >
            AI Engineering Intelligence
          </Link>
          <div className="flex items-center gap-4 text-sm text-zinc-400">
            <span>{user.login}</span>
            <button
              onClick={handleLogout}
              className="rounded-md border border-zinc-700 px-3 py-1 text-zinc-300 hover:bg-zinc-800"
            >
              Log out
            </button>
          </div>
        </div>
      </header>
      <main className="mx-auto max-w-5xl px-6 py-8">{children}</main>
    </div>
  );
}
