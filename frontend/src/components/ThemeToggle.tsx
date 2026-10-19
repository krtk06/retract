import { AnimatePresence, m } from "motion/react";

import { EASE } from "../lib/motion";
import { useTheme } from "../lib/theme";
import { Icon } from "./Icon";

export function ThemeToggle({ className = "" }: { className?: string }) {
  const { theme, toggle } = useTheme();
  const next = theme === "dark" ? "light" : "dark";

  function handleToggle() {
    // The flip is one continuous inversion: enable global colour transitions
    // for the duration of the switch only, so the rest of the app stays free
    // of blanket transition rules.
    const root = document.documentElement;
    root.classList.add("theme-transition");
    window.setTimeout(() => root.classList.remove("theme-transition"), 420);
    toggle();
  }

  return (
    <button
      onClick={handleToggle}
      aria-label={`Switch to ${next} theme`}
      title={`Switch to ${next} theme`}
      className={`btn btn--icon btn--ghost overflow-hidden ${className}`}
    >
      <AnimatePresence mode="wait" initial={false}>
        <m.span
          key={theme}
          className="grid place-items-center"
          initial={{ opacity: 0, rotate: -40, scale: 0.7 }}
          animate={{ opacity: 1, rotate: 0, scale: 1 }}
          exit={{ opacity: 0, rotate: 40, scale: 0.7 }}
          transition={{ duration: 0.18, ease: EASE }}
        >
          <Icon name={theme === "dark" ? "sun" : "moon"} size={16} />
        </m.span>
      </AnimatePresence>
    </button>
  );
}
