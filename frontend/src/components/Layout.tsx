import { useQueryClient } from "@tanstack/react-query";
import { m } from "motion/react";
import type { ReactNode } from "react";
import { Link, NavLink } from "react-router-dom";
import { api } from "../api/client";
import type { User } from "../api/types";
import { EASE } from "../lib/motion";
import { Icon } from "./Icon";
import { ThemeToggle } from "./ThemeToggle";
import { VerifyEmailBanner } from "./VerifyEmailBanner";

/**
 * The app shell: a sticky top bar over a persistent navigation rail, with the
 * content column on the document's own scroll.
 *
 * The scroll decision is deliberate. A top bar that sticks and a rail that sticks
 * are easy; adding a *third* nested scroll region behind them is not, and this app
 * already has two (the findings table scrolls horizontally, the agent transcript
 * vertically). So the content column keeps normal page scroll and only the rail
 * scrolls independently.
 */
const NAV = [
  { to: "/", label: "Dashboard", icon: "dashboard", end: true },
  { to: "/repos", label: "Repositories", icon: "repo", end: false },
] as const;

export function Layout({ user, children }: { user: User; children: ReactNode }) {
  const queryClient = useQueryClient();

  async function handleLogout() {
    await api.logout();
    await queryClient.invalidateQueries({ queryKey: ["me"] });
    window.location.reload();
  }

  return (
    <div className="paper min-h-[100dvh] bg-canvas">
      <a href="#content" className="skip">
        Skip to content
      </a>

      <header className="topbar relative sticky top-0 z-40">
        {/* The masthead rule draws once, like a printed line being struck. */}
        <m.span
          aria-hidden="true"
          className="absolute inset-x-0 bottom-[-1px] h-px origin-left bg-line-strong"
          initial={{ scaleX: 0 }}
          animate={{ scaleX: 1 }}
          transition={{ duration: 0.5, ease: EASE }}
        />
        <Link to="/" className="flex items-center gap-2.5">
          <span className="text-ink">
            <Icon name="logo" size={20} />
          </span>
          <span className="font-display text-[17px] font-semibold tracking-tight text-ink">
            Retract
          </span>
        </Link>

        <span className="ml-auto flex items-center gap-2">
          <ThemeToggle />
          <span className="hidden max-w-[10rem] truncate text-[13px] text-muted sm:block">
            {user.login}
          </span>
          <button onClick={handleLogout} className="btn btn--ghost" aria-label="Log out">
            <Icon name="logout" size={15} />
            <span className="hidden sm:inline">Log out</span>
          </button>
        </span>
      </header>

      <div className="mx-auto w-full max-w-[1280px] px-4 lg:flex lg:gap-8 lg:px-6">
        <nav
          aria-label="Primary"
          className="hidden shrink-0 flex-col gap-1 py-8 lg:sticky lg:top-[52px] lg:flex lg:h-[calc(100dvh-52px)] lg:w-[232px]"
        >
          {NAV.map((item) => (
            <NavLink key={item.to} to={item.to} end={item.end} className="tab tab--side tab--motion relative">
              {({ isActive }) => (
                <>
                  {isActive && (
                    <m.span
                      aria-hidden="true"
                      layoutId="rail-ink"
                      className="absolute left-0 top-1.5 bottom-1.5 w-px bg-ink"
                      transition={{ duration: 0.28, ease: EASE }}
                    />
                  )}
                  <Icon name={item.icon} size={16} />
                  {item.label}
                </>
              )}
            </NavLink>
          ))}

          <span className="inset mt-auto p-3">
            <span className="label block">Signed in</span>
            <span className="mt-1 block truncate text-[13px] text-ink">{user.login}</span>
          </span>
        </nav>

        {/* Below lg the rail becomes a horizontal tab strip under the top bar.
            No hamburger, no drawer — the navigation stays visible. */}
        <nav
          aria-label="Primary"
          className="tabs sticky top-[52px] z-30 -mx-4 mb-2 flex overflow-x-auto bg-canvas px-4 lg:hidden"
        >
          {NAV.map((item) => (
            <NavLink key={item.to} to={item.to} end={item.end} className="tab tab--motion relative">
              {({ isActive }) => (
                <>
                  {item.label}
                  {isActive && (
                    <m.span
                      aria-hidden="true"
                      layoutId="strip-ink"
                      className="absolute -bottom-px left-2 right-2 h-0.5 bg-ink"
                      transition={{ duration: 0.28, ease: EASE }}
                    />
                  )}
                </>
              )}
            </NavLink>
          ))}
        </nav>

        <main id="content" className="min-w-0 flex-1 pb-24 pt-8 lg:pt-10">
          <VerifyEmailBanner />
          {children}
        </main>
      </div>

      <p className="mx-auto max-w-[1280px] border-t border-line px-4 pb-8 pt-4 text-center font-mono text-[11px] text-faint lg:px-6">
        <Link to="/" className="link">
          Retract
        </Link>{" "}
        — repository health, computed not vibes
      </p>
    </div>
  );
}
