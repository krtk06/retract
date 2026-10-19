import { useEffect, useRef, useState } from "react";

/** One curve for the whole dossier. Mass, not bounce. */
export const EASE = [0.16, 1, 0.3, 1] as const;

/**
 * Fires once when the element first enters the viewport.
 *
 * Falls back to "already visible" whenever IntersectionObserver does not exist
 * (jsdom in tests, very old browsers): content must never depend on a watcher
 * that may be absent to become visible.
 */
export function useInViewOnce<T extends Element>(margin = "0px 0px -12% 0px") {
  const ref = useRef<T | null>(null);
  const [inView, setInView] = useState(false);

  useEffect(() => {
    const el = ref.current;
    if (!el || typeof IntersectionObserver === "undefined") {
      setInView(true);
      return;
    }
    const observer = new IntersectionObserver(
      (entries) => {
        for (const entry of entries) {
          if (entry.isIntersecting) {
            setInView(true);
            observer.disconnect();
          }
        }
      },
      { rootMargin: margin, threshold: 0.12 },
    );
    observer.observe(el);
    return () => observer.disconnect();
  }, [margin]);

  return { ref, inView };
}

/**
 * Sibling stagger, capped. A list appears as a list; beyond the cap the tail
 * arrives as one quiet block rather than a wave.
 */
export function stagger(index: number, step = 0.045, cap = 0.34) {
  return Math.min(index * step, cap);
}
