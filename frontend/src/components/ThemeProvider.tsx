import { useCallback, useEffect, useMemo, useState, type ReactNode } from "react";

import {
  THEME_STORAGE_KEY,
  ThemeContext,
  applyTheme,
  initialTheme,
  type Theme,
} from "../lib/theme";

export function ThemeProvider({ children }: { children: ReactNode }) {
  const [theme, setTheme] = useState<Theme>(initialTheme);

  // Apply on every change; persist only an explicit choice. Writing the
  // system-derived value on mount would freeze it into storage, and a later OS
  // theme change would no longer be followed.
  useEffect(() => {
    applyTheme(theme);
  }, [theme]);

  const toggle = useCallback(() => {
    setTheme((current) => {
      const next = current === "dark" ? "light" : "dark";
      try {
        window.localStorage.setItem(THEME_STORAGE_KEY, next);
      } catch {
        // Private-mode storage can throw; the theme still applies this session.
      }
      return next;
    });
  }, []);

  const value = useMemo(() => ({ theme, toggle }), [theme, toggle]);

  return <ThemeContext.Provider value={value}>{children}</ThemeContext.Provider>;
}
