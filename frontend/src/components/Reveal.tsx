import { m, useReducedMotion } from "motion/react";
import type { ReactNode } from "react";

import { EASE } from "../lib/motion";

/**
 * A section arriving once, on its own scroll, with a short rise. Below-fold
 * content waits; above-fold content arrives immediately. Reduced motion keeps
 * the fade and drops the travel.
 */
export function Reveal({
  children,
  delay = 0,
  y = 8,
  className,
}: {
  children: ReactNode;
  delay?: number;
  y?: number;
  className?: string;
}) {
  const reduced = useReducedMotion();
  return (
    <m.div
      className={className}
      initial={{ opacity: 0, y: reduced ? 0 : y }}
      whileInView={{ opacity: 1, y: 0 }}
      viewport={{ once: true, margin: "-12% 0px" }}
      transition={{ duration: 0.42, ease: EASE, delay: reduced ? 0 : delay }}
    >
      {children}
    </m.div>
  );
}
