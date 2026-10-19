import type { ReactNode } from "react";
import { Link } from "react-router-dom";
import { Icon, type IconName } from "./Icon";

export interface EmptyStateProps {
  title: string;
  detail?: string;
  action?: { label: string; to: string } | ReactNode;
  icon?: IconName;
}

/**
 * The app had nine inline empty / error / "nothing here" blocks and eight bare
 * "Loading…" strings, each styled slightly differently and none of them
 * announcing anything to assistive tech. Two components, one frame.
 */
export function EmptyState({ title, detail, action, icon = "logo" }: EmptyStateProps) {
  return (
    <div className="inset flex flex-col items-center gap-3 p-8 text-center">
      {/* A quiet float: the page is breathing, not frozen. Static under
          reduced motion. */}
      <span className="anim-float text-faint">
        <Icon name={icon} size={24} />
      </span>
      <p className="text-[13px] font-medium text-ink">{title}</p>
      {detail ? <p className="max-w-[32rem] text-[13px] text-muted">{detail}</p> : null}
      {action ? (
        typeof action === "object" && action !== null && "to" in action ? (
          <Link to={action.to} className="btn btn--primary sheen press">
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
      <p className="label">{label}</p>
      {Array.from({ length: rows }, (_, index) => (
        <span key={index} aria-hidden="true" className="skeleton h-9" />
      ))}
    </div>
  );
}
