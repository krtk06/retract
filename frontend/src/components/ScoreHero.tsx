import { useTheme } from "../lib/theme";
import { Meter, ScoreRing } from "./Meter";
import { PILLARS, PILLAR_COLOR_VAR, PILLAR_LABELS, scoreTone } from "../lib/palette";
import type { Score } from "../api/types";

export function ScoreHero({ score }: { score: Score | null }) {
  const { theme } = useTheme();
  if (!score) return null;

  return (
    <section className="anim-step-in px-panel p-5">
      <div className="flex flex-wrap items-center gap-6">
        <div className="relative shrink-0">
          <ScoreRing value={score.overall} tone={scoreTone(score.overall)} theme={theme} />
        </div>
        <div className="min-w-[16rem] flex-1">
          <p className="px-eyebrow">Repository health</p>
          {score.previous_overall != null ? (
            <p className="font-ui text-[11px] text-muted">
              {score.overall - score.previous_overall >= 0 ? "▲" : "▼"}{" "}
              {Math.abs(score.overall - score.previous_overall)} vs previous
            </p>
          ) : null}
          {score.basis === "count" && (
            <p className="px-badge px-badge--flat mt-2 border-warn text-warn">
              No LOC measured — scored on finding count
            </p>
          )}
        </div>
      </div>

      <div className="mt-5 flex flex-col gap-2 border-t-2 border-line pt-4">
        {PILLARS.map((pillar) => {
          const data = score.pillars[pillar];
          if (!data) return null;
          // A pillar with no findings scores 100, which is indistinguishable from
          // "checked and clean" unless it is labelled. Nothing was found because
          // nothing was measured, and the number must not read as reassurance.
          const unmeasured = data.findings === 0;
          return (
            <div key={pillar} className="flex items-center gap-3">
              <span className="w-[7rem] shrink-0 font-ui text-[9px] uppercase tracking-[0.06em] text-muted">
                {PILLAR_LABELS[pillar]}
              </span>
              <Meter
                value={unmeasured ? null : data.score}
                label={PILLAR_LABELS[pillar]}
                color={`var(${PILLAR_COLOR_VAR[pillar]})`}
              />
              <span className="w-[8.5rem] shrink-0 text-right font-mono text-[10px] text-faint tabular-nums">
                {unmeasured
                  ? "not measured"
                  : `${data.verified}v / ${data.hypotheses}h${
                      data.dismissed != null ? ` / ${data.dismissed}d` : ""
                    }`}
              </span>
            </div>
          );
        })}
      </div>

      {PILLARS.some((pillar) => score.pillars[pillar]?.findings === 0) && (
        <p className="mt-4 border-t-2 border-line pt-3 text-[11px] leading-relaxed text-faint">
          A dimension with no findings is shown as &ldquo;not measured&rdquo;: nothing
          was found because nothing triggered that analyzer, which is not the same
          as clean.
        </p>
      )}
    </section>
  );
}
