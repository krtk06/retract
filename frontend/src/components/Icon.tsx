import {
  Activity,
  AlertTriangle,
  ArrowLeft,
  ArrowRight,
  Ban,
  Check,
  ChevronDown,
  ChevronRight,
  Clock,
  Copy,
  Download,
  ExternalLink,
  Folder,
  LayoutGrid,
  LogOut,
  Moon,
  Plus,
  Search,
  Shield,
  Sun,
  X,
} from "lucide-react";
import type { ComponentType, ReactNode } from "react";

/**
 * One stroke-icon set for the whole app: lucide-react's crisp 2px strokes on a
 * 24×24 grid, plus two drawn marks (the logo pulse and the GitHub mark) that no
 * icon library should own. The `name`-based API is kept so call sites read the
 * same; only the glyph source moved.
 */

const LUCIDE: Record<string, ComponentType<{ size?: number | string; strokeWidth?: number | string }>> = {
  dashboard: LayoutGrid,
  repo: Folder,
  sun: Sun,
  moon: Moon,
  check: Check,
  x: X,
  ban: Ban,
  alert: AlertTriangle,
  copy: Copy,
  download: Download,
  external: ExternalLink,
  search: Search,
  plus: Plus,
  activity: Activity,
  shield: Shield,
  clock: Clock,
  logout: LogOut,
  "chevron-down": ChevronDown,
  "chevron-right": ChevronRight,
  "arrow-left": ArrowLeft,
  "arrow-right": ArrowRight,
};

/** Marks drawn here, not bought: the logo pulse and the GitHub mark. */
const DRAWN: Record<string, ReactNode> = {
  logo: (
    <>
      <rect x="3" y="3" width="18" height="18" rx="5" />
      <path d="M7 12.5h2.2l1.6-3.5 2.3 7 1.7-3.5H17" />
    </>
  ),
  github: (
    <path d="M9 19c-4.5 1.4-4.5-2.3-6.3-2.8m12.6 5.4v-3.6c0-1 .1-1.4-.5-2 2.7-.3 5.4-1.3 5.4-5.9a4.6 4.6 0 0 0-1.2-3.2 4.3 4.3 0 0 0-.1-3.1s-1-.3-3.3 1.2a11.4 11.4 0 0 0-6 0C7.3 3.5 6.3 3.8 6.3 3.8a4.3 4.3 0 0 0-.1 3.2A4.6 4.6 0 0 0 5 10.2c0 4.6 2.7 5.6 5.4 5.9-.6.6-.6 1.2-.5 2V21" />
  ),
};

export const ICONS = { ...DRAWN, ...LUCIDE } as const;

export type IconName = keyof typeof ICONS;

export interface IconProps {
  name: IconName;
  /** Rendered size in CSS pixels. Defaults to 16. */
  size?: number;
  className?: string;
  /** Supplying this makes the icon labelled; omitting it marks it decorative. */
  title?: string;
}

export function Icon({ name, size = 16, className, title }: IconProps) {
  const labels = title ? { role: "img" as const, "aria-label": title } : { "aria-hidden": true };
  const drawn = DRAWN[name];
  const Glyph = LUCIDE[name];

  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth={1.75}
      strokeLinecap="round"
      strokeLinejoin="round"
      className={className}
      {...labels}
    >
      {title ? <title>{title}</title> : null}
      {drawn}
      {Glyph ? <Glyph size={size} strokeWidth={1.75} /> : null}
    </svg>
  );
}
