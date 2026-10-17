import { useQueryClient } from "@tanstack/react-query";
import type { ReactNode } from "react";
import { Link, NavLink } from "react-router-dom";
import { api } from "../api/client";
import type { User } from "../api/types";
import { PixelIcon } from "./PixelIcon";
import { ThemeToggle } from "./ThemeToggle";
import { VerifyEmailBanner } from "./VerifyEmailBanner";

/**
 * The app as a window: a 28px title bar, a sidebar, and content that scrolls on
 * the document.
 *
 * The scroll decision is deliberate. A title bar that sticks and a sidebar that
 * sticks are easy; adding a *third* nested scroll region behind them is not, and
 * this app already has two (the findings table scrolls horizontally, the agent
 * transcript scrolls vertically). So the content column keeps normal page scroll
 * and only the sidebar scrolls independently.
 */
export function Layout({ user, children }: { user: User; children: ReactNode }) {
  const queryClient = useQueryClient();

  async function handleLogout() {
    await api.logout();
    await queryClient.invalidateQueries({ queryKey: ["me"] });
    window.location.reload();
  }

  return (
    <div className="min-h-[100dvh] bg-canvas">
      <a href="#content" className="px-skip">
        Skip to content
      </a>

      <header className="px-titlebar sticky top-0 z-40 justify-between">
        <span className="flex items-center gap-2">
          <PixelIcon name="logo" size={12} className="text-accent" />
          <span className="font-ui text-[13px] font-bold tracking-[0.18em] text-ink">
            RETRACT
          </span>
        </span>

        <span className="ml-auto flex items-center gap-3">
          {/* Decorative window controls. They imply minimise/maximise/close, so
              they are aria-hidden and carry no behaviour — every function they
              might suggest is available as a labelled control beside them. */}
          <span className="flex gap-1">
            <span data-window-dot aria-hidden="true" className="block h-[8px] w-[8px] bg-danger" />
            <span data-window-dot aria-hidden="true" className="block h-[8px] w-[8px] bg-warn" />
            <span data-window-dot aria-hidden="true" className="block h-[8px] w-[8px] bg-ok" />
          </span>
          <ThemeToggle />
          <span className="max-w-[10rem] truncate font-ui text-[9px] text-muted">
            {user.login}
          </span>
          <button onClick={handleLogout} className="px-btn px-btn--quiet">
            Log out
          </button>
        </span>
      </header>

      <div className="mx-auto flex max-w-[1280px] gap-0 px-0 sm:px-4">
        <nav
          aria-label="Primary"
          className="sticky top-[28px] hidden h-[calc(100dvh-28px)] w-[200px] shrink-0 flex-col gap-1 border-r-2 border-line bg-surface p-2 lg:flex"
        >
          <NavLink to="/" end className="px-tab px-tab--side">
            Dashboard
          </NavLink>
          <NavLink to="/repos" className="px-tab px-tab--side">
            Repositories
          </NavLink>

          <span className="mt-auto px-well p-2">
            <span className="block font-ui text-[9px] tracking-[0.16em] text-faint">
              SIGNED IN
            </span>
            <span className="block truncate font-ui text-[11px] text-ink">{user.login}</span>
          </span>
        </nav>

        {/* Below lg the sidebar becomes a tab strip directly under the title bar.
            No hamburger, no drawer — a drawer hides the window metaphor this
            whole design is built on. */}
        <nav
          aria-label="Primary"
          className="px-tabs sticky top-[28px] z-30 w-full overflow-x-auto lg:hidden"
        >
          <NavLink to="/" end className="px-tab">
            Dashboard
          </NavLink>
          <NavLink to="/repos" className="px-tab">
            Repositories
          </NavLink>
        </nav>

        <main id="content" className="min-w-0 flex-1 px-4 pb-24 pt-6 sm:px-6">
          <VerifyEmailBanner />
          {children}
        </main>
      </div>

      <p className="mx-auto max-w-[1280px] px-4 pb-6 text-center font-mono text-[10px] text-faint sm:px-6">
        <Link to="/" className="px-link">
          Retract
        </Link>{" "}
        — repository health, computed not vibes
      </p>
    </div>
  );
}