import type { ReactNode } from "react";
import { Link } from "react-router-dom";
import { PixelIcon, type PixelIconName } from "./PixelIcon";

export interface EmptyStateProps {
  title: string;
  detail?: string;
  action?: { label: string; to: string } | ReactNode;
  icon?: PixelIconName;
}

/**
 * The app had nine inline empty / error / "nothing here" blocks and eight bare
 * "Loading…" strings, each styled slightly differently and none of them
 * announcing anything to assistive tech. Two components, one frame.
 */
export function EmptyState({ title, detail, action, icon = "logo" }: EmptyStateProps) {
  return (
    <div className="px-well flex flex-col items-center gap-3 p-8 text-center">
      <span className="text-faint">
        <PixelIcon name={icon} size={24} />
      </span>
      <p className="font-ui text-[11px] uppercase tracking-[0.06em] text-ink">{title}</p>
      {detail ? <p className="max-w-[32rem] text-[13px] text-muted">{detail}</p> : null}
      {action ? (
        typeof action === "object" && action !== null && "to" in action ? (
          <Link to={action.to} className="px-btn px-btn--primary">
            {action.label}
          </Link>
        ) : (
          action
        )
      ) : null}
    </div>
  );
}

export function Loading({ label, rows = 3 }: { label: string; rows?: number }) {
  return (
    <div role="status" aria-live="polite" className="flex flex-col gap-2">
      <p className="px-eyebrow">{label}</p>
      {Array.from({ length: rows }, (_, index) => (
        <span
          key={index}
          aria-hidden="true"
          className="px-dither block h-[28px] border-2 border-line"
        />
      ))}
    </div>
  );
}
