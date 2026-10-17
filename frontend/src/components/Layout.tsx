import { useQueryClient } from "@tanstack/react-query";
import type { ReactNode } from "react";
import { Link, NavLink } from "react-router-dom";

import { api } from "../api/client";
import type { User } from "../api/types";
import { ThemeToggle } from "./ThemeToggle";
import { VerifyEmailBanner } from "./VerifyEmailBanner";

function navClass({ isActive }: { isActive: boolean }): string {
  return `px-3.5 py-1.5 text-sm font-medium transition-all duration-300 ease-step ${
    isActive ? "bg-accent-soft text-ink" : "text-muted hover:bg-surface-2 hover:text-ink"
  }`;
}

export function Layout({ user, children }: { user: User; children: ReactNode }) {
  const queryClient = useQueryClient();

  async function handleLogout() {
    await api.logout();
    await queryClient.invalidateQueries({ queryKey: ["me"] });
    window.location.reload();
  }

  return (
    <div className="min-h-[100dvh]">
      <a href="#content" className="px-skip">
        Skip to content
      </a>

      <header className="sticky top-0 z-40 px-3 pt-3 sm:px-4 sm:pt-4">
        <div className="mx-auto flex max-w-6xl flex-wrap items-center gap-2">
          <nav className="px-panel flex items-center gap-1 p-1.5 pl-4">
            <Link
              to="/"
              className="flex items-center gap-2 pr-2 text-[15px] font-extrabold tracking-tight text-ink"
            >
              <span
                aria-hidden="true"
                className="h-2.5 w-2.5"
                style={{
                  background:
                    "radial-gradient(circle at 35% 30%, var(--accent-strong), var(--accent))",
                  boxShadow: "0 0 14px var(--accent-glow)",
                }}
              />
              Retract
            </Link>
            <span aria-hidden="true" className="mx-1 hidden h-4 w-px bg-line sm:block" />
            <NavLink to="/" end className={navClass}>
              Dashboard
            </NavLink>
            <NavLink to="/repos" className={navClass}>
              Repositories
            </NavLink>
          </nav>

          <div className="ml-auto flex items-center">
            <div className="px-panel flex items-center gap-2 p-1.5 pl-2.5 sm:pl-3.5">
              <span className="hidden max-w-32 truncate text-sm text-muted sm:inline">
                {user.login}
              </span>
              <ThemeToggle />
              <button
                onClick={handleLogout}
                className="px-btn px-btn--ghost px-3.5 py-1.5 text-xs"
              >
                Log out
              </button>
            </div>
          </div>
        </div>
      </header>

      <main id="content" className="mx-auto max-w-6xl px-4 pb-24 pt-8 sm:px-6">
        <VerifyEmailBanner />
        {children}
      </main>
    </div>
  );
}
