import { useMemo, useState } from "react";
import { m } from "motion/react";

import { useRemediation } from "../api/hooks";
import type { Effort, RemediationItem, RemediationPlan, Repository } from "../api/types";
import { EASE, stagger } from "../lib/motion";
import { PILLAR_LABELS, SEVERITY_COLOR_VAR, type Pillar } from "../lib/palette";
import { EmptyState } from "./EmptyState";
import { Icon } from "./Icon";

/**
 * The fix plan: what to fix, in what order, and what it is worth.
 *
 * Two numbers appear on this component and they are not the same kind of number,
 * which is why the labels are explicit rather than decorative.
 *
 * The headline (`58 → 92`) is exact. It is the platform's own scoring curve run
 * over a repository with none of these findings, so it is what actually happens if
 * the work gets done.
 *
 * The per-item `+N` is the gain **in that item's own pillar**, not a share of the
 * headline. The curve is nonlinear (`100 / (1 + density / 30)`) and the overall is
 * capped at `worst_pillar + 15`, so on a repository drowning in security findings,
 * clearing all of security moves the overall by almost nothing until some other
 * pillar becomes the worst. A card reading "+0 pts" on the single most valuable
 * fix in the repository would be arithmetically true and actively misleading.
 *
 * So the item number is measured where the work actually lands, no total is ever
 * computed by summing the items, and the ranking uses
 * `weighted_penalty_removed / effort` — additive and order-independent, which
 * makes the ordering reliable independently of either displayed figure.
 */

const EFFORT_STYLES: Record<Effort, string> = {
  low: "text-ok border-ok/40",
  medium: "text-warn border-warn/40",
  high: "text-danger border-danger/40",
};

const QUICK_WIN_COUNT = 3;

/**
 * A short, readable label for a reference URL.
 *
 * Two links both captioned "reference" tells the reader nothing; the host plus the
 * most specific path segment says what the link actually is ("OWASP", "GitHub
 * docs", "radon"), which is what they need to decide whether to open it.
 */
function referenceLabel(url: string): string {
  try {
    const parsed = new URL(url);
    const segment = parsed.pathname.split("/").filter(Boolean).pop() ?? "";
    if (parsed.hostname.includes("owasp.org")) return "OWASP";
    if (parsed.hostname.includes("github.com")) return "GitHub docs";
    if (parsed.hostname.includes("peps.python.org")) return "Python PEP";
    if (parsed.hostname.includes("pytest.org")) return "pytest docs";
    if (parsed.hostname.includes("radon")) return "radon docs";
    if (parsed.hostname.includes("osv.dev")) return "OSV";
    if (segment) return `${parsed.hostname.replace(/^www\./, "")} · ${segment}`;
    return parsed.hostname.replace(/^www\./, "");
  } catch {
    return url;
  }
}

function blobUrl(repository: Repository | null, commitSha: string | null, path: string | null, line: number | null) {
  if (!repository || repository.url.startsWith("local://") || !path) return null;
  const ref = commitSha ?? repository.default_branch;
  return `${repository.url}/blob/${ref}/${path}${line ? `#L${line}` : ""}`;
}

export function RemediationPlanPanel({
  analysisId,
  repository,
  commitSha,
  onOpenAgent,
}: {
  analysisId: number;
  repository: Repository | null;
  commitSha: string | null;
  onOpenAgent?: () => void;
}) {
  const query = useRemediation(analysisId, true);
  const plan = query.data;

  if (query.isLoading) {
    return <p className="text-[13px] text-faint">Building the fix plan…</p>;
  }
  if (query.isError) {
    return (
      <p className="panel px-4 py-4 text-[13px] text-muted">
        The fix plan is unavailable for this analysis.
      </p>
    );
  }
  if (!plan || plan.work_items.length === 0) {
    return (
      <section className="panel anim-in p-5">
        <h3 className="text-[15px] font-semibold text-ink">Fix plan</h3>
        <EmptyState title="Nothing to fix. No open findings were recorded." />
      </section>
    );
  }

  return <PlanBody plan={plan} repository={repository} commitSha={commitSha} onOpenAgent={onOpenAgent} />;
}

function PlanBody({
  plan,
  repository,
  commitSha,
  onOpenAgent,
}: {
  plan: RemediationPlan;
  repository: Repository | null;
  commitSha: string | null;
  onOpenAgent?: () => void;
}) {
  const [pillarFilter, setPillarFilter] = useState("");
  const quickWins = useMemo(() => plan.work_items.slice(0, QUICK_WIN_COUNT), [plan]);
  const pillars = useMemo(() => {
    const present = new Set(plan.work_items.map((item) => item.pillar));
    return [...present].sort();
  }, [plan]);
  // Rank is carried alongside the item so a key and a displayed position survive
  // filtering: the rank is the item's place in the full ranking, not in the view.
  const visible = useMemo(
    () =>
      plan.work_items
        .map((item, index) => ({ item, rank: index + 1 }))
        .filter(({ item }) => !pillarFilter || item.pillar === pillarFilter),
    [plan, pillarFilter],
  );

  return (
    <section className="panel anim-in p-6">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <p className="label">Fix plan</p>
          <p className="mt-1.5 flex flex-wrap items-baseline gap-3">
            <span className="figure text-2xl text-faint">
              {plan.current_overall ?? "—"}
            </span>
            <span className="text-xl text-faint/60">
              <Icon name="arrow-right" size={18} />
            </span>
            <span className="figure text-2xl" style={{ color: "var(--ok)" }}>
              {plan.projected_overall ?? "—"}
            </span>
            <span className="text-[13px] text-muted">
              if every item below is fixed
              {plan.recoverable_points != null && ` (+${plan.recoverable_points})`}
            </span>
          </p>
        </div>
        <div className="flex flex-col items-end gap-2.5 text-right">
          <p className="text-[12px] text-faint tabular-nums">
            {plan.work_items.length} work {plan.work_items.length === 1 ? "item" : "items"} ·{" "}
            {plan.findings_considered} findings
          </p>
          <div className="flex gap-2">
            <a
              href={`/api/analyses/${plan.analysis_id}/remediation.md`}
              download
              className="link inline-flex items-center gap-1.5"
            >
              <Icon name="download" size={14} />
              Download .md
            </a>
            {onOpenAgent && (
              <button type="button" onClick={onOpenAgent} className="btn btn--ghost">
                Deep fix plan with the agent
              </button>
            )}
          </div>
        </div>
      </div>

      <p className="mt-4 text-[12px] leading-relaxed text-faint text-pretty">
        The headline is this platform&rsquo;s own scoring curve applied to a repository with none of
        these findings, so it is exact. Each card&rsquo;s <span className="text-ink/80">+N</span>{" "}
        is the gain <span className="text-ink/80">in that item&rsquo;s own pillar</span>, not a share
        of the headline: the overall is capped at the worst pillar plus 15, so fixing anything but
        the current worst can move it very little. Use the order, not a sum.
      </p>

      {quickWins.length > 0 && (
        <div className="inset mt-6 p-4">
          <h4 className="label">Quickest wins</h4>
          <ul className="mt-3 space-y-2">
            {quickWins.map((item, index) => (
              <li
                // Keyed on the ranked position, not `item.key`: two work items can
                // share a category (two different vulnerable packages), and duplicate
                // keys make React reuse the wrong element — which silently breaks the
                // expand control on the card below.
                key={`${index}-${item.action}`}
                className="flex flex-wrap items-baseline gap-2 text-[13px]"
              >
                <span className="text-ink">{item.action}</span>
                {item.pillar_points > 0 && (
                  <span className="text-[12px] font-medium text-ok tabular-nums">
                    +{item.pillar_points} pts
                  </span>
                )}
                <span className="text-[12px] text-faint">
                  {item.effort} effort ·{" "}
                  {PILLAR_LABELS[item.pillar as Pillar] ?? item.pillar} · {item.finding_count}{" "}
                  {item.finding_count === 1 ? "finding" : "findings"}
                </span>
              </li>
            ))}
          </ul>
        </div>
      )}

      {plan.unverified_items > 0 && (
        <p className="mt-4 rounded-[2px] border border-hypo/40 bg-hypo-soft px-4 py-2.5 text-[12px] text-hypo">
          {plan.unverified_items} of these {plan.unverified_items === 1 ? "item rests" : "items rest"}{" "}
          on an unverified hypothesis. Review those before scheduling the work.
        </p>
      )}

      {pillars.length > 1 && (
        <div className="mt-5 flex flex-wrap gap-2 text-[13px]">
          <select
            value={pillarFilter}
            onChange={(event) => setPillarFilter(event.target.value)}
            className="input select w-auto"
            aria-label="Filter the fix plan by pillar"
          >
            <option value="">All areas</option>
            {pillars.map((pillar) => (
              <option key={pillar} value={pillar}>
                {PILLAR_LABELS[pillar as Pillar] ?? pillar}
              </option>
            ))}
          </select>
        </div>
      )}

      <ul className="mt-4 space-y-3">
        {visible.map(({ item, rank }, index) => (
          <WorkItemCard
            key={`${rank}-${item.action}`}
            item={item}
            rank={rank}
            repository={repository}
            commitSha={commitSha}
            index={index}
          />
        ))}
      </ul>

      {plan.truncated_findings > 0 && (
        <p className="mt-4 text-[12px] text-faint">
          {plan.truncated_findings} further findings were grouped into work items beyond the
          display limit. The downloaded Markdown contains the ranking it was cut from.
        </p>
      )}
    </section>
  );
}

function WorkItemCard({
  item,
  rank,
  repository,
  commitSha,
  index = 0,
}: {
  item: RemediationItem;
  rank: number;
  repository: Repository | null;
  commitSha: string | null;
  index?: number;
}) {
  const [open, setOpen] = useState(false);
  const [showFindings, setShowFindings] = useState(false);

  return (
    <m.li
      layout
      initial={{ opacity: 0, y: 6 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.34, ease: EASE, delay: stagger(index, 0.045, 0.3) }}
      className="card p-4"
    >
      <div className="flex flex-wrap items-center gap-2">
        <span className="text-[12px] font-medium text-faint tabular-nums">#{rank}</span>
        <span
          className="chip chip--flat"
          style={{
            borderColor: `var(${SEVERITY_COLOR_VAR[item.severity]})`,
            color: `var(${SEVERITY_COLOR_VAR[item.severity]})`,
          }}
        >
          {item.severity}
        </span>
        <p className="text-[13px] font-medium text-ink text-pretty">{item.action}</p>
        <span
          className={`rounded-[2px] border px-1.5 py-0.5 text-[10px] font-medium ${EFFORT_STYLES[item.effort]}`}
        >
          {item.effort} effort
        </span>
        {item.source === "llm:eve" && (
          <span
            className="chip chip--flat"
            style={{ borderColor: "var(--hypo)", color: "var(--hypo)" }}
          >
            agent-authored
          </span>
        )}
        {/* A zero here is real, not a bug: on a small repository the density curve is
            saturated, so clearing one pillar rounds to the same score. Showing
            "+0 pts" would read as a broken feature, so the badge yields to the
            penalty count in the subline instead. */}
        {item.pillar_points > 0 && (
          <span
            className="ml-auto text-[12px] font-medium text-ok tabular-nums"
            title={`What fixing this is worth in the ${PILLAR_LABELS[item.pillar as Pillar] ?? item.pillar} pillar. These values do not add up to the headline.`}
          >
            +{item.pillar_points} pts
          </span>
        )}
      </div>

      <p className="mt-1.5 text-[12px] text-faint">
        {PILLAR_LABELS[item.pillar as Pillar] ?? item.pillar} · {item.finding_count}{" "}
        {item.finding_count === 1 ? "finding" : "findings"} · removes{" "}
        {item.weighted_penalty_removed} penalty points
        {item.pillar_points === 0 && " · already saturated at this repository's density"}
      </p>

      {open ? (
        <m.div
          className="mt-3 space-y-3 overflow-hidden"
          initial={{ opacity: 0, height: 0 }}
          animate={{ opacity: 1, height: "auto" }}
          transition={{ duration: 0.28, ease: EASE }}
        >
          <ol className="list-decimal space-y-2 pl-5 text-[13px] leading-relaxed text-muted">
            {item.steps.map((step) => (
              <li key={step}>{step}</li>
            ))}
          </ol>
          <p className="text-[12px] text-faint">
            <span className="font-medium text-ink/80">Verify:</span> {item.verify}
          </p>
          {item.references.length > 0 && (
            <ul className="flex flex-wrap gap-3 text-[12px]">
              {item.references.map((reference) => (
                <li key={reference}>
                  <a href={reference} target="_blank" rel="noreferrer" className="link inline-flex items-center gap-1">
                    {referenceLabel(reference)}
                    <Icon name="external" size={12} />
                  </a>
                </li>
              ))}
            </ul>
          )}
          <div>
            <button type="button" onClick={() => setShowFindings((value) => !value)} className="btn btn--ghost">
              {showFindings ? "hide findings" : `show ${item.finding_count} findings`}
            </button>
            {showFindings && (
              <m.ul
                className="mt-2.5 space-y-1.5 overflow-hidden text-[12px]"
                initial={{ opacity: 0, height: 0 }}
                animate={{ opacity: 1, height: "auto" }}
                transition={{ duration: 0.24, ease: EASE }}
              >
                {item.findings.map((finding) => {
                  const href = blobUrl(repository, commitSha, finding.file_path, finding.line_start);
                  return (
                    <li key={finding.finding_id} className="flex flex-wrap items-baseline gap-2">
                      <span className="text-faint">[{finding.severity}]</span>
                      <span className="text-muted">{finding.title}</span>
                      {finding.file_path && (
                        <span className="font-mono text-faint/80">
                          {finding.file_path}
                          {finding.line_start ? `:${finding.line_start}` : ""}
                        </span>
                      )}
                      {href && (
                        <a href={href} target="_blank" rel="noreferrer" className="link inline-flex items-center gap-1">
                          on GitHub
                          <Icon name="external" size={12} />
                        </a>
                      )}
                    </li>
                  );
                })}
              </m.ul>
            )}
          </div>
        </m.div>
      ) : (
        <button type="button" onClick={() => setOpen(true)} className="btn btn--ghost mt-2.5 press">
          show the steps
        </button>
      )}
    </m.li>
  );
}

/**
 * The compact card that closes the Overview tab.
 *
 * Deliberately a summary, not a second full plan: the plan itself lives behind the
 * link so the findings table keeps the page's attention, while the reader still
 * learns the headline number and the cheapest next step without clicking.
 */
export function RemediationSummaryCard({
  analysisId,
  onOpen,
}: {
  analysisId: number;
  onOpen: () => void;
}) {
  const query = useRemediation(analysisId, true);
  const plan = query.data;
  if (query.isLoading || query.isError || !plan || plan.work_items.length === 0) {
    return null;
  }

  const best = plan.work_items[0];
  return (
    <section className="panel anim-in flex flex-wrap items-center justify-between gap-4 p-5">
      <div>
        <h3 className="text-[15px] font-semibold text-ink">How to fix these issues</h3>
        <p className="mt-1.5 text-[13px] text-muted">
          {plan.work_items.length} work {plan.work_items.length === 1 ? "item" : "items"} ·{" "}
          <span className="font-medium text-ink">
            {plan.current_overall} → {plan.projected_overall}
          </span>{" "}
          if all are fixed
        </p>
        {best && (
          <p className="mt-1.5 text-[13px] text-faint">
            Start with <span className="text-ink/80">{best.action}</span>
            {best.pillar_points > 0 && ` (+${best.pillar_points} pts)`} · {best.effort} effort
          </p>
        )}
      </div>
      <button type="button" onClick={onOpen} className="btn btn--primary">
        Open fix plan
        <Icon name="arrow-right" size={14} />
      </button>
    </section>
  );
}
