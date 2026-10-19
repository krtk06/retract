import { CountUp } from "./CountUp";
import { useInViewOnce } from "../lib/motion";

/**
 * A proportional meter: a track and a fill. It is the one bar primitive shared by
 * the pillar rows, verification coverage and human acceptance, so those read as
 * one instrument rather than three unrelated bars.
 *
 * A `null` value is "nobody measured this" — drawn as a hatched track and an em
 * dash, never as zero and never as a full bar, because unmeasured is not clean.
 *
 * The fill settles onto its tick rule the first time the meter scrolls into
 * view, and the figure counts with it; both arrive as one gesture.
 */
export interface MeterProps {
  /** `null` means "nobody measured this" — not zero, and not a full bar either. */
  value: number | null;
  label: string;
  color?: string;
  /** Transitions the fill when it enters view. Off in tests. */
  animate?: boolean;
  /** Milliseconds to hold before the fill settles. The pillar stagger uses this. */
  delay?: number;
}

export function Meter({ value, label, color = "var(--accent)", animate = true, delay = 0 }: MeterProps) {
  const unmeasured = value === null;
  const pct = unmeasured ? 0 : Math.max(0, Math.min(100, value));
  const { ref, inView } = useInViewOnce<HTMLDivElement>();

  return (
    <div
      ref={ref}
      className="flex min-w-0 flex-1 items-center gap-2.5"
      role="progressbar"
      aria-label={label}
      aria-valuenow={value ?? undefined}
      aria-valuemin={0}
      aria-valuemax={100}
    >
      <span
        className="tick-rule relative h-[3px] min-w-0 flex-1 overflow-hidden"
        role="presentation"
      >
        {unmeasured ? (
          <span
            aria-hidden="true"
            data-unmeasured="true"
            className="absolute inset-0"
            style={{
              backgroundImage:
                "repeating-linear-gradient(45deg, var(--line-strong) 0 3px, transparent 3px 7px)",
            }}
          />
        ) : (
          <span
            data-filled="true"
            className="absolute inset-y-0 left-0"
            style={{
              width: `${inView ? pct : 0}%`,
              background: color,
              transition: animate ? `width 520ms var(--ease-out) ${delay}ms` : undefined,
            }}
          />
        )}
      </span>
      <span className="figure w-8 shrink-0 text-right text-sm text-ink">
        {unmeasured ? "—" : <CountUp value={value} duration={0.7} delay={delay / 1000} />}
      </span>
    </div>
  );
}
