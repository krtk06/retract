import { useEffect, useState } from "react";

import type { Score } from "../api/types";

const PILLAR_LABELS: Record<string, string> = {
  "code-quality": "Code Quality",
  security: "Security",
  testing: "Testing",
  documentation: "Documentation",
  dependencies: "Dependencies",
  architecture: "Architecture",
};

const PILLAR_ORDER = [
  "security",
  "code-quality",
  "testing",
  "architecture",
  "documentation",
  "dependencies",
];

function tone(score: number): string {
  if (score >= 80) return "var(--ok)";
  if (score >= 60) return "var(--info)";
  if (score >= 40) return "var(--warn)";
  return "var(--danger)";
}

function AnimatedNumber({ value }: { value: number }) {
  const [display, setDisplay] = useState(0);
  useEffect(() => {
    const duration = 700;
    const start = performance.now();
    let frame = 0;
    const tick = (now: number) => {
      const progress = Math.min(1, (now - start) / duration);
      setDisplay(Math.round(value * (1 - Math.pow(1 - progress, 3))));
      if (progress < 1) frame = requestAnimationFrame(tick);
    };
    frame = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(frame);
  }, [value]);
  return <>{display}</>;
}

function Delta({ delta }: { delta: number | null | undefined }) {
  if (delta == null) return null;
  if (delta === 0) {
    return <span className="text-xs text-faint">no change vs previous</span>;
  }
  const up = delta > 0;
  return (
    <span
      className={`px-badge border ${
        up ? "border-ok/30 bg-ok-soft text-ok" : "border-danger/30 bg-danger-soft text-danger"
      }`}
    >
      {up ? "▲" : "▼"} {up ? "+" : ""}
      {delta} vs previous
    </span>
  );
}

export function ScoreHero({ score }: { score: Score | null }) {
  if (!score) return null;
  const pillars = PILLAR_ORDER.map((key) => ({
    key,
    label: PILLAR_LABELS[key],
    data: score.pillars[key],
  })).filter((p) => p.data);

  const overall = score.overall;
  const color = tone(overall);

  return (
    <section className="px-panel anim-step-in p-6 sm:p-7">
      <div className="flex flex-wrap items-center justify-between gap-6">
        <div className="flex items-center gap-6">
          <div className="relative grid h-28 w-28 shrink-0 place-items-center">
            <span
              aria-hidden="true"
              className="absolute inset-0"
              style={{
                background: `conic-gradient(${color} ${overall * 3.6}deg, var(--line) 0deg)`,
                filter: `drop-shadow(0 0 16px ${color})`,
                opacity: 0.9,
              }}
            />
            <span
              aria-hidden="true"
              className="absolute inset-[7px]"
              style={{ background: "var(--surface)" }}
            />
            <span
              className="relative text-4xl font-extrabold tabular-nums tracking-tighter"
              style={{ color }}
            >
              <AnimatedNumber value={overall} />
            </span>
          </div>
          <div>
            <p className="px-eyebrow">Repository health score</p>
            <p className="mt-1.5 text-sm text-muted">
              out of <span className="text-ink">100</span>
            </p>
            <div className="mt-3">
              <Delta delta={score.delta} />
            </div>
          </div>
        </div>

        <div className="text-right text-xs text-faint">
          {score.loc != null && score.kloc != null && (
            <p className="tabular-nums">
              {score.loc.toLocaleString()} LOC · {score.kloc} KLOC
            </p>
          )}
          {score.basis === "count" && <p className="mt-1">No LOC measured — scored on finding count</p>}
        </div>
      </div>

      <div className="mt-7 space-y-3.5">
        {pillars.map(({ key, label, data }) => {
          // A pillar with no findings scores 100, which is indistinguishable from
          // "checked and clean" unless it is labelled. Nothing was found because
          // nothing was measured, and the number should not read as reassurance.
          const unmeasured = data.findings === 0;
          const color = tone(data.score);
          return (
            <div key={key} className="flex items-center gap-3">
              <span className="w-32 shrink-0 text-sm text-muted">{label}</span>
              <div className="h-2.5 flex-1 overflow-hidden bg-surface-2 ring-1 ring-line">
                {unmeasured ? (
                  <div
                    className="h-full w-full bg-line"
                    role="progressbar"
                    aria-valuenow={data.score}
                    aria-valuemin={0}
                    aria-valuemax={100}
                    aria-label={`${label} not measured: no findings, so no score is claimed`}
                  />
                ) : (
                  <div
                    className="h-full"
                    style={{
                      width: `${data.score}%`,
                      background: `linear-gradient(90deg, color-mix(in oklab, ${color} 55%, transparent), ${color})`,
                      boxShadow: `0 0 12px color-mix(in oklab, ${color} 40%, transparent)`,
                      transition: "width 800ms cubic-bezier(0.32, 0.72, 0, 1)",
                    }}
                    role="progressbar"
                    aria-valuenow={data.score}
                    aria-valuemin={0}
                    aria-valuemax={100}
                    aria-label={`${label} score`}
                  />
                )}
              </div>
              <span
                className={`w-8 text-right text-sm font-semibold tabular-nums ${
                  unmeasured ? "text-faint" : "text-ink"
                }`}
              >
                {unmeasured ? "—" : data.score}
              </span>
              <span
                className="w-28 text-right text-xs text-faint tabular-nums"
                title={
                  unmeasured
                    ? "no findings — this dimension was not exercised, which is not the same as clean"
                    : "verified / hypothesis / dismissed"
                }
              >
                {unmeasured ? (
                  <span className="text-faint/70">not measured</span>
                ) : (
                  <>
                    {data.verified}v / {data.hypotheses}h
                    {data.dismissed != null ? ` / ${data.dismissed}d` : ""}
                  </>
                )}
              </span>
            </div>
          );
        })}
      </div>
      {pillars.some((p) => p.data.findings === 0) && (
        <p className="mt-4 text-xs leading-relaxed text-faint">
          A dimension with no findings is shown as &ldquo;not measured&rdquo;: nothing was
          found because nothing triggered that analyzer, which is not the same as clean.
        </p>
      )}
    </section>
  );
}
