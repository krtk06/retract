import { STATUS_COLOR_VAR, type RunStatus } from "../lib/palette";

const FALLBACK: RunStatus = "pending";

/**
 * Status is never colour alone: the word is always present, and the glyph
 * blinks only while work is actually in flight.
 */
export function StatusPill({ status }: { status: string }) {
  const key = (status in STATUS_COLOR_VAR ? status : FALLBACK) as RunStatus;
  const color = `var(${STATUS_COLOR_VAR[key]})`;
  const live = key === "running";

  return (
    <span
      className="px-badge"
      style={{ borderColor: color, color }}
    >
      <span
        aria-hidden="true"
        className={`block h-[8px] w-[8px] ${live ? "anim-blink" : ""}`}
        style={{ background: color }}
      />
      {status}
    </span>
  );
}
