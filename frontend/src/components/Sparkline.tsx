import { m, useReducedMotion } from "motion/react";

import { EASE } from "../lib/motion";

/**
 * A run-over-run trend line. Where a single score is a point, this is the shape
 * of the history around it — the thing that tells a reader whether a number is a
 * blip or a direction.
 *
 * The line draws itself once on mount; the head dot lands after it. Reduced
 * motion gets the finished line in the same frame.
 *
 * Renders nothing with fewer than two points, because a line needs a slope.
 */
export interface SparklineProps {
  values: number[];
  width?: number;
  height?: number;
  className?: string;
  color?: string;
}

export function Sparkline({
  values,
  width = 120,
  height = 36,
  className = "",
  color = "var(--accent)",
}: SparklineProps) {
  const reduced = useReducedMotion();
  if (values.length < 2) return null;

  const min = Math.min(...values);
  const max = Math.max(...values);
  const span = max - min || 1;
  const stepX = width / (values.length - 1);
  const points = values.map((value, index) => {
    const x = index * stepX;
    const y = height - ((value - min) / span) * (height - 6) - 3;
    return `${x.toFixed(1)} ${y.toFixed(1)}`;
  });
  const last = points[points.length - 1].split(" ").map(Number);
  const d = points.map((point, index) => `${index === 0 ? "M" : "L"}${point}`).join(" ");

  return (
    <svg
      width={width}
      height={height}
      viewBox={`0 0 ${width} ${height}`}
      className={className}
      style={{ color }}
      aria-hidden="true"
    >
      <m.path
        d={d}
        fill="none"
        stroke="currentColor"
        strokeWidth={2}
        strokeLinecap="round"
        strokeLinejoin="round"
        initial={reduced ? false : { pathLength: 0 }}
        animate={{ pathLength: 1 }}
        transition={{ duration: reduced ? 0 : 0.9, ease: EASE }}
      />
      <m.circle
        cx={last[0]}
        cy={last[1]}
        r={2.5}
        fill="currentColor"
        initial={reduced ? false : { opacity: 0 }}
        animate={{ opacity: 1 }}
        transition={{ duration: reduced ? 0 : 0.2, ease: EASE, delay: reduced ? 0 : 0.7 }}
      />
    </svg>
  );
}
