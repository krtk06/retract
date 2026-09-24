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
  "code-quality",
  "security",
  "testing",
  "documentation",
  "dependencies",
  "architecture",
];

function barColor(score: number): string {
  if (score >= 80) return "bg-emerald-500";
  if (score >= 60) return "bg-lime-500";
  if (score >= 50) return "bg-amber-500";
  if (score >= 25) return "bg-orange-500";
  return "bg-red-500";
}

export function ScorePanel({ score }: { score: Score | null }) {
  if (!score) return null;
  const pillars = PILLAR_ORDER.map((key) => ({
    key,
    label: PILLAR_LABELS[key],
    data: score.pillars[key],
  })).filter((p) => p.data);

  return (
    <section className="rounded-lg border border-zinc-800 bg-zinc-900 p-5">
      <div className="flex items-baseline justify-between">
        <h3 className="font-semibold">Health Score</h3>
        <p className="text-xs text-zinc-500">
          {score.loc != null && <>{score.loc.toLocaleString()} LOC · </>}v{score.version}
        </p>
      </div>
      <div className="mt-4 flex items-center gap-4">
        <div className="text-4xl font-bold" aria-label="Overall score">
          {score.overall}
          <span className="text-lg text-zinc-500">/100</span>
        </div>
      </div>
      <div className="mt-5 space-y-3">
        {pillars.map(({ key, label, data }) => (
          <div key={key} className="flex items-center gap-3">
            <span className="w-32 shrink-0 text-sm text-zinc-400">{label}</span>
            <div className="h-2.5 flex-1 overflow-hidden rounded-full bg-zinc-800">
              <div
                className={`h-full rounded-full transition-all duration-500 ${barColor(data.score)}`}
                style={{ width: `${data.score}%` }}
                role="progressbar"
                aria-valuenow={data.score}
                aria-valuemin={0}
                aria-valuemax={100}
                aria-label={`${label} score`}
              />
            </div>
            <span className="w-10 text-right text-sm font-medium">{data.score}</span>
            <span className="w-24 text-right text-xs text-zinc-500">
              {data.verified}v / {data.hypotheses}h
            </span>
          </div>
        ))}
      </div>
    </section>
  );
}
