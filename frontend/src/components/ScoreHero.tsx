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

function barColor(score: number): string {
  if (score >= 80) return "bg-emerald-500";
  if (score >= 60) return "bg-lime-500";
  if (score >= 50) return "bg-amber-500";
  if (score >= 25) return "bg-orange-500";
  return "bg-red-500";
}

function overallTone(score: number): string {
  if (score >= 80) return "text-emerald-400";
  if (score >= 60) return "text-lime-400";
  if (score >= 50) return "text-amber-400";
  if (score >= 25) return "text-orange-400";
  return "text-red-400";
}

function AnimatedNumber({ value }: { value: number }) {
  const [display, setDisplay] = useState(0);
  useEffect(() => {
    const duration = 600;
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
    return <span className="text-sm text-zinc-500">no change vs previous</span>;
  }
  const up = delta > 0;
  return (
    <span className={`text-sm font-medium ${up ? "text-emerald-400" : "text-red-400"}`}>
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

  return (
    <section className="rounded-lg border border-zinc-800 bg-zinc-900 p-6">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <p className="text-sm uppercase tracking-wide text-zinc-500">Repository Health Score</p>
          <p className="mt-1 flex items-baseline gap-3">
            <span className={`text-5xl font-bold ${overallTone(score.overall)}`}>
              <AnimatedNumber value={score.overall} />
            </span>
            <span className="text-lg text-zinc-500">/ 100</span>
          </p>
        </div>
        <div className="text-right">
          <Delta delta={score.delta} />
          {score.loc != null && (
            <p className="mt-1 text-xs text-zinc-500">
              {score.loc.toLocaleString()} LOC · {score.kloc} KLOC
            </p>
          )}
        </div>
      </div>

      <div className="mt-6 space-y-3">
        {pillars.map(({ key, label, data }) => {
          // A pillar with no findings scores 100, which is indistinguishable from
          // "checked and clean" unless it is labelled. Nothing was found because
          // nothing was measured, and the number should not read as reassurance.
          const unmeasured = data.findings === 0;
          return (
            <div key={key} className="flex items-center gap-3">
              <span className="w-32 shrink-0 text-sm text-zinc-400">{label}</span>
              <div className="h-2.5 flex-1 overflow-hidden rounded-full bg-zinc-800">
                {unmeasured ? (
                  <div
                    className="h-full w-full rounded-full bg-zinc-800"
                    role="progressbar"
                    aria-valuenow={data.score}
                    aria-valuemin={0}
                    aria-valuemax={100}
                    aria-label={`${label} not measured: no findings, so no score is claimed`}
                  />
                ) : (
                  <div
                    className={`h-full rounded-full ${barColor(data.score)}`}
                    style={{
                      width: `${data.score}%`,
                      transition: "width 700ms cubic-bezier(0.22, 1, 0.36, 1)",
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
                className={`w-8 text-right text-sm font-medium ${unmeasured ? "text-zinc-600" : ""}`}
              >
                {unmeasured ? "—" : data.score}
              </span>
              <span
                className="w-28 text-right text-xs text-zinc-500"
                title={
                  unmeasured
                    ? "no findings — this dimension was not exercised, which is not the same as clean"
                    : "verified / hypothesis / dismissed"
                }
              >
                {unmeasured ? (
                  <span className="text-zinc-600">not measured</span>
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
        <p className="mt-3 text-xs text-zinc-600">
          A dimension with no findings is shown as &ldquo;not measured&rdquo;: nothing was
          found because nothing triggered that analyzer, which is not the same as clean.
        </p>
      )}
    </section>
  );
}
