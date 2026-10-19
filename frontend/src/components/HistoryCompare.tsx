import { useState } from "react";
import { useNavigate } from "react-router-dom";

import { useCompare, useHistory } from "../api/hooks";
import type { AnalysisHistoryItem } from "../api/types";
import { Sparkline } from "./Sparkline";
import { Icon } from "./Icon";
import { PILLAR_LABELS, type Pillar } from "../lib/palette";

function Delta({ value }: { value: number }) {
  if (value === 0) return <span className="text-faint">—</span>;
  const up = value > 0;
  return (
    <span className={`chip chip--flat tabular-nums ${up ? "text-ok" : "text-danger"}`}>
      {up ? "+" : ""}
      {value}
    </span>
  );
}

function statusBadge(item: AnalysisHistoryItem) {
  if (item.status !== "done") {
    return <span className="chip chip--flat bg-surface-2 text-muted">{item.status}</span>;
  }
  return <span className="chip chip--flat bg-ok-soft text-ok">done</span>;
}

export function HistoryCompare({ analysisId }: { analysisId: number }) {
  const navigate = useNavigate();
  const history = useHistory(analysisId, true);
  const [left, setLeft] = useState<number | null>(null);
  const [right, setRight] = useState<number | null>(null);
  const comparison = useCompare(left, right);

  if (history.isLoading) {
    return <p className="text-[13px] text-muted">Loading analysis history…</p>;
  }
  const items = history.data ?? [];
  if (items.length <= 1) {
    return (
      <section className="panel p-6">
        <h3 className="text-[15px] font-semibold text-ink">History</h3>
        <p className="mt-2 text-[13px] leading-relaxed text-muted text-pretty">
          This is the first analysis for this repository. Re-run it after changes to compare
          scores over time.
        </p>
      </section>
    );
  }

  const trend = items
    .map((item) => item.overall)
    .filter((value): value is number => value != null);

  return (
    <section className="panel p-6">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h3 className="text-[15px] font-semibold text-ink">Analysis history</h3>
          <p className="mt-1 text-[12px] text-faint">Select two runs to compare scores side-by-side.</p>
        </div>
        {trend.length >= 2 && <Sparkline values={trend} width={140} height={36} />}
      </div>
      <ul className="mt-3 space-y-2">
        {items.map((item) => (
          <li
            key={item.id}
            className="flex flex-wrap items-center gap-2.5 rounded-[2px] border border-line bg-surface-2 px-3.5 py-2.5 text-[13px]"
          >
            <button
              onClick={() => navigate(`/analyses/${item.id}`)}
              className="font-mono text-accent hover:underline"
            >
              #{item.id}
            </button>
            {statusBadge(item)}
            <span className="text-faint">
              {item.created_at ? new Date(item.created_at).toLocaleString() : ""}
            </span>
            <span className="font-mono text-[11px] text-faint/80">
              {item.commit_sha ? item.commit_sha.slice(0, 8) : "—"}
            </span>
            <span className="text-[12px] text-faint tabular-nums">{item.finding_count} findings</span>
            {item.overall != null && (
              <span className="text-[13px] font-semibold text-ink tabular-nums">
                {item.overall}/100
              </span>
            )}
            <span className="ml-auto flex gap-1.5">
              <button
                onClick={() => setLeft(item.id)}
                className={`btn ${left === item.id ? "btn--primary" : "btn--ghost"}`}
              >
                A
              </button>
              <button
                onClick={() => setRight(item.id)}
                className={`btn ${right === item.id ? "btn--primary" : "btn--ghost"}`}
              >
                B
              </button>
            </span>
          </li>
        ))}
      </ul>

      {left != null && right != null && (
        <div className="inset anim-in mt-5 p-4">
          <h4 className="flex items-center gap-1.5 text-[13px] font-semibold text-ink">
            Comparison: <span className="font-mono text-info">#{left}</span>
            <Icon name="arrow-right" size={13} className="text-faint" />
            <span className="font-mono text-info">#{right}</span>
          </h4>
          {comparison.isLoading && <p className="mt-2 text-[12px] text-faint">Loading comparison…</p>}
          {comparison.data && (
            <>
              <p className="mt-2 flex items-center gap-2 text-[13px] text-muted">
                Overall{" "}
                <span className="flex items-center gap-1.5 text-ink">
                  {comparison.data.left.overall ?? "—"}
                  <Icon name="arrow-right" size={13} className="text-faint" />
                  {comparison.data.right.overall ?? "—"}
                </span>{" "}
                <Delta value={comparison.data.overall_delta ?? 0} />
              </p>
              <table className="mt-3 w-full text-[13px]">
                <thead>
                  <tr className="text-left text-[11px] text-faint">
                    <th className="pb-1.5 font-medium">Pillar</th>
                    <th className="pb-1.5 font-medium">A</th>
                    <th className="pb-1.5 font-medium">B</th>
                    <th className="pb-1.5 text-right font-medium">Δ</th>
                  </tr>
                </thead>
                <tbody>
                  {comparison.data.pillars.map((pillar) => (
                    <tr key={pillar.pillar} className="border-t border-line">
                      <td className="py-1.5 text-ink">
                        {PILLAR_LABELS[pillar.pillar as Pillar] ?? pillar.pillar}
                      </td>
                      <td className="py-1.5 text-muted tabular-nums">{pillar.left_score}</td>
                      <td className="py-1.5 text-muted tabular-nums">{pillar.right_score}</td>
                      <td className="py-1.5 text-right">
                        <Delta value={pillar.delta} />
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </>
          )}
          {comparison.isError && (
            <p className="mt-2 text-[12px] text-danger">Could not compare these analyses.</p>
          )}
        </div>
      )}
    </section>
  );
}
