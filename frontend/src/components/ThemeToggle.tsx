import { PixelIcon } from "./PixelIcon";
import { useTheme } from "../lib/theme";

export function ThemeToggle({ className = "" }: { className?: string }) {
  const { theme, toggle } = useTheme();
  const next = theme === "dark" ? "light" : "dark";

  return (
    <button
      onClick={toggle}
      aria-label={`Switch to ${next} theme`}
      title={`Switch to ${next} theme`}
      className={`px-btn px-btn-icon ${className}`}
    >
      {/* keyed on theme so the swap steps rather than crossfades */}
      <span key={theme} className="anim-step-in block">
        <PixelIcon name={theme === "dark" ? "sun" : "moon"} size={12} />
      </span>
    </button>
  );
}