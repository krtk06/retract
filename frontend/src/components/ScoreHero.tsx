import { m, useReducedMotion } from "motion/react";
import { CountUp } from "./CountUp";
import { Meter } from "./Meter";
import { Icon } from "./Icon";
import { PILLARS, PILLAR_COLOR_VAR, PILLAR_LABELS, scoreTone, TONE_VERDICT_WORD, type Tone } from "../lib/palette";
import type { Score } from "../api/types";

/**
 * The dossier's verdict page: the score as a stamped report figure, the pillars
 * as a numbered schedule. This reveal is the one authored motion moment in the
 * app — the numeral counts up once, the verdict stamp lands, the pillars settle
 * onto their rules in sequence — and everything else stays still.
 */

const TONE_COLOR: Record<Tone, string> = {
  ok: "var(--ok)",
  info: "var(--info)",
  warn: "var(--warn)",
  danger: "var(--danger)",
};

const TONE_GLYPH: Record<Tone, "check" | "alert"> = {
  ok: "check",
  info: "check",
  warn: "alert",
  danger: "alert",
};

export function ScoreHero({ score }: { score: Score | null }) {
  const reduced = useReducedMotion();
  if (!score) return null;

  const delta = score.previous_overall != null ? score.overall - score.previous_overall : null;
  const tone = scoreTone(score.overall);

  return (
    <section className="panel anim-in p-6">
      <div className="flex flex-wrap items-end justify-between gap-6">
        <div className="flex flex-wrap items-center gap-5">
          <p className="figure text-6xl text-ink">
            <CountUp value={score.overall} />
            <span className="font-sans text-lg font-normal text-faint">/100</span>
          </p>
          <div>
            <m.span
              className="stamp"
              style={{ color: TONE_COLOR[tone] }}
              initial={reduced ? false : { opacity: 0, scale: 1.12 }}
              animate={{ opacity: 1, scale: 1 }}
              transition={{ duration: 0.24, ease: [0.16, 1, 0.3, 1], delay: reduced ? 0 : 0.9 }}
            >
              <Icon name={TONE_GLYPH[tone]} size={11} />
              {TONE_VERDICT_WORD[tone]}
            </m.span>
            <p className="label mt-1.5">Repository health</p>
          </div>
        </div>
        <div className="flex flex-col items-end gap-3">
          {delta != null && (
            <p className="flex items-center gap-1.5 text-[13px] text-muted">
              <Icon
                name={delta >= 0 ? "arrow-right" : "arrow-left"}
                size={14}
                className={delta >= 0 ? "text-ok" : "text-danger"}
              />
              <span className={delta >= 0 ? "text-ok" : "text-danger"}>
                {delta >= 0 ? "+" : ""}
                {delta}
              </span>
              vs previous run
            </p>
          )}
          {score.basis === "count" && (
            <p className="chip border-warn/40 text-warn">
              <Icon name="alert" size={13} />
              No LOC measured — scored on finding count
            </p>
          )}
        </div>
      </div>

      <div className="mt-6 flex flex-col gap-3.5 border-t border-line pt-5">
        {PILLARS.map((pillar, index) => {
          const data = score.pillars[pillar];
          if (!data) return null;
          // A pillar with no findings scores 100, which is indistinguishable from
          // "checked and clean" unless it is labelled. Nothing was found because
          // nothing was measured, and the number must not read as reassurance.
          const unmeasured = data.findings === 0;
          return (
            <div key={pillar} className="flex flex-wrap items-center gap-x-3 gap-y-1.5 sm:flex-nowrap">
              <span className="w-[7rem] shrink-0 text-[13px] text-muted">
                <span className="mr-1.5 font-mono text-[11px] text-faint tabular-nums">
                  {String(index + 1).padStart(2, "0")}
                </span>
                {PILLAR_LABELS[pillar]}
              </span>
              <Meter
                value={unmeasured ? null : data.score}
                label={PILLAR_LABELS[pillar]}
                color={`var(${PILLAR_COLOR_VAR[pillar]})`}
                delay={200 + index * 60}
              />
              {/* The v/h/d ledger is detail: at phone widths the meter keeps the
                  width it needs to stay readable, and the counts step aside. */}
              <span className="hidden w-[8.5rem] shrink-0 text-right font-mono text-[11px] text-faint tabular-nums sm:block">
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
        <p className="mt-5 border-t border-line pt-4 text-[13px] leading-relaxed text-faint">
          A dimension with no findings is shown as &ldquo;not measured&rdquo;: nothing was found
          because nothing triggered that analyzer, which is not the same as clean.
        </p>
      )}
    </section>
  );
}
