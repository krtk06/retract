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
          <div className="flex items-center gap-5">
            <Link
              to="/"
              className="text-lg font-semibold tracking-tight text-zinc-300 hover:text-white hover:underline"
            >
              AI Engineering Intelligence
            </Link>
            <nav className="flex gap-4 text-sm">
              <Link to="/" className="text-zinc-400 hover:text-zinc-200">
                Dashboard
              </Link>
              <Link to="/repos" className="text-zinc-400 hover:text-zinc-200">
                Repositories
              </Link>
            </nav>
          </div>
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
