import { animate, m, useMotionValue, useReducedMotion, useTransform } from "motion/react";
import { useEffect, useState } from "react";

import { EASE } from "../lib/motion";

/**
 * A figure that counts to its value once. After the count it renders the
 * literal number so selection and assistive tech see a real value, not a
 * motion node. Reduced motion gets the final value immediately.
 */
export function CountUp({
  value,
  decimals = 0,
  duration = 0.9,
  delay = 0,
}: {
  value: number;
  decimals?: number;
  duration?: number;
  delay?: number;
}) {
  const reduced = useReducedMotion();
  const mv = useMotionValue(0);
  const text = useTransform(mv, (latest) => latest.toFixed(decimals));
  const [done, setDone] = useState(false);

  useEffect(() => {
    if (reduced) {
      mv.set(value);
      setDone(true);
      return;
    }
    const controls = animate(mv, value, {
      duration,
      delay,
      ease: EASE,
      onComplete: () => setDone(true),
    });
    return () => controls.stop();
  }, [mv, value, reduced, duration, delay]);

  if (done) return <>{value.toFixed(decimals)}</>;
  return <m.span>{text}</m.span>;
}
