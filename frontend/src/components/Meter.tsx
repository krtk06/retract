import { colorFor, type Theme } from "../lib/palette";

/**
 * One 20-cell meter unit, 5% per cell, shared by four displays: the score ring,
 * the six pillar meters, verification coverage, and human acceptance by category.
 * They share it so they read as one instrument instead of four unrelated bars.
 *
 * Cells are discrete rather than a continuous fill because that is the point of
 * the whole aesthetic — and because a cell grid survives being resized and
 * scaled without looking like a gradient that happens to be thin.
 */
export const METER_CELLS = 20;

const TONE_VAR: Record<"ok" | "info" | "warn" | "danger", string> = {
  ok: "var(--ok)",
  info: "var(--info)",
  warn: "var(--warn)",
  danger: "var(--danger)",
};

export interface MeterProps {
  /** `null` means "nobody measured this" — not zero, and not a full bar either. */
  value: number | null;
  label: string;
  color?: string;
  animate?: boolean;
}

export function Meter({ value, label, color = "var(--accent)", animate = true }: MeterProps) {
  const filled = value === null ? 0 : Math.round((Math.min(value, 100) / 100) * METER_CELLS);

  return (
    <div
      className="flex items-center gap-2"
      role="progressbar"
      aria-label={label}
      aria-valuenow={value ?? undefined}
      aria-valuemin={0}
      aria-valuemax={100}
    >
      <span
        className={`flex gap-[2px] border-2 border-line bg-canvas p-[2px] ${
          value === null ? "px-dither border-line-strong" : ""
        }`}
      >
        {Array.from({ length: METER_CELLS }, (_, index) => (
          <span
            key={index}
            data-lit={index < filled}
            className="block h-[8px] w-[8px] transition-colors duration-300"
            style={
              value === null
                ? undefined
                : {
                    background: index < filled ? color : "var(--line-strong)",
                    opacity: index < filled ? 1 : 0.35,
                    animation: animate && index < filled ? "cell-on 480ms steps(4, end) both" : undefined,
                    animationDelay: animate ? `${index * 40}ms` : undefined,
                  }
            }
          />
        ))}
      </span>
      <span className="w-9 shrink-0 text-right font-ui text-[13px] tabular-nums">
        {value === null ? "—" : Math.round(value)}
      </span>
    </div>
  );
}

export interface ScoreRingProps {
  value: number;
  tone?: "ok" | "info" | "warn" | "danger";
  theme: Theme;
  size?: number;
}

/**
 * The smooth conic-gradient donut is gone. This is 20 rectangles placed around a
 * circle by rotation, which is what a segmented gauge looks like when it has to
 * render on whole pixels. The segments are rectangles rather than arcs precisely
 * because arcs cannot be crisp.
 */
export function ScoreRing({ value, tone = "ok", theme, size = 132 }: ScoreRingProps) {
  const filled = Math.round((Math.min(Math.max(value, 0), 100) / 100) * METER_CELLS);
  const ringColor = colorFor(TONE_VAR[tone], theme);
  const radius = size / 2 - 9;

  return (
    <div className="grid place-items-center" style={{ width: size, height: size }}>
      <svg width={size} height={size} viewBox={`0 0 ${size} ${size}`} aria-hidden="true">
        {Array.from({ length: METER_CELLS }, (_, index) => {
          // An unlit segment cannot use `fill="var(--line-strong)"`: a CSS
          // variable is only valid in the `fill` *property*, never in the
          // presentation attribute. Hence style, not fill.
          const isLit = index < filled;
          const degrees = (index / METER_CELLS) * 360 - 90;
          return (
            <rect
              key={index}
              data-lit={isLit}
              x={size / 2 - 3}
              y={size / 2 - radius - 5}
              width={6}
              height={10}
              transform={`rotate(${degrees} ${size / 2} ${size / 2})`}
              style={{
                fill: isLit ? ringColor : "var(--line-strong)",
                opacity: isLit ? 1 : 0.35,
                animation: isLit ? "cell-on 480ms steps(4, end) both" : undefined,
                animationDelay: isLit ? `${index * 30}ms` : undefined,
              }}
            />
          );
        })}
      </svg>
      <span
        className="absolute font-ui text-[40px] leading-none tabular-nums"
        style={{ color: ringColor }}
      >
        {value}
      </span>
    </div>
  );
}
