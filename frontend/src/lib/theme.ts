import { createContext, useContext } from "react";

export type Theme = "dark" | "light";

export const THEME_STORAGE_KEY = "retract-theme";

/**
 * First paint follows the system preference (`prefers-color-scheme`); an
 * explicit choice persisted to localStorage wins afterwards. The inline script
 * in index.html applies the same value before paint. Outside a window (SSR,
 * tests) the fallback is dark.
 */
export function initialTheme(): Theme {
  if (typeof window === "undefined") return "dark";
  try {
    const stored = window.localStorage.getItem(THEME_STORAGE_KEY);
    if (stored === "light" || stored === "dark") return stored;
  } catch {
    return "dark";
  }
  // jsdom and very old browsers have no matchMedia: dark is the documented
  // fallback, and it is stated here rather than inferred from a crash.
  if (typeof window.matchMedia !== "function") return "dark";
  return window.matchMedia("(prefers-color-scheme: light)").matches ? "light" : "dark";
}

export function applyTheme(theme: Theme) {
  const root = document.documentElement;
  root.classList.toggle("dark", theme === "dark");
  root.style.colorScheme = theme;
}

export interface ThemeContextValue {
  theme: Theme;
  toggle: () => void;
}

export const ThemeContext = createContext<ThemeContextValue | null>(null);

/**
 * The context is required. A component rendered outside the provider is a
 * wiring bug, and returning a fake theme would hide it behind a toggle that
 * does nothing — the failure a user cannot explain.
 */
export function useTheme(): ThemeContextValue {
  const context = useContext(ThemeContext);
  if (context === null) {
    throw new Error("useTheme must be used within a ThemeProvider");
  }
  return context;
}
