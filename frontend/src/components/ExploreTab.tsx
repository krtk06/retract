import { useMemo, useState } from "react";

import { useGraphSummary, useGraphSymbols, useNeighborhood } from "../api/hooks";
import type { GraphLink, SymbolRef } from "../api/types";
import { EmptyState, Loading } from "./EmptyState";

function KindBadge({ kind }: { kind: string }) {
  // A symbol kind is classification, not evidence: the dossier reserves hue for
  // severity, status and verification, so kinds are a flat mono ticket.
  return (
    <span className="chip chip--flat font-mono text-[10px] text-muted">{kind}</span>
  );
}

function LinkList({
  title,
  links,
  field,
  onSelect,
}: {
  title: string;
  links: GraphLink[];
  field: "source" | "target";
  onSelect: (name: string) => void;
}) {
  if (links.length === 0) return null;
  return (
    <div>
      <h5 className="label">{title}</h5>
      <ul className="mt-2 space-y-1">
        {links.map((link, index) => (
          <li key={index} className="inset flex items-center gap-2 px-3 py-2 text-[13px]">
            <button
              onClick={() => onSelect(link[field])}
              className="min-w-0 truncate text-left font-mono text-accent hover:underline"
              title={link[field]}
            >
              {link[field]}
            </button>
            <span className="ml-auto shrink-0 text-[10px] uppercase text-faint">{link.kind}</span>
          </li>
        ))}
      </ul>
    </div>
  );
}

function NeighborhoodPanel({
  analysisId,
  root,
  onSelect,
}: {
  analysisId: number;
  root: string | null;
  onSelect: (name: string) => void;
}) {
  const neighborhood = useNeighborhood(analysisId, root);

  const outgoing = useMemo(
    () => (neighborhood.data?.links ?? []).filter((l) => l.source === root),
    [neighborhood.data, root],
  );
  const incoming = useMemo(
    () => (neighborhood.data?.links ?? []).filter((l) => l.target === root),
    [neighborhood.data, root],
  );

  return (
    <section className="panel p-5">
      <h4 className="text-[13px] font-semibold text-ink">Dependency view</h4>
      {!root && <p className="mt-2 text-[12px] text-faint">Select a symbol to inspect its dependencies.</p>}
      {root && neighborhood.isLoading && <Loading label="Loading…" />}
      {root && neighborhood.data && (
        <div className="mt-3 space-y-3">
          <p className="font-mono text-[13px] text-ink">
            {root}
            {neighborhood.data.root && (
              <span className="ml-2 text-[11px] text-faint">
                {neighborhood.data.root.file_path}:{neighborhood.data.root.line_start}
              </span>
            )}
          </p>
          <div className="grid grid-cols-1 gap-4">
            <LinkList title="Depends on" links={outgoing} field="target" onSelect={onSelect} />
            <LinkList title="Used by" links={incoming} field="source" onSelect={onSelect} />
          </div>
          {neighborhood.data.links.length === 0 && (
            <p className="text-[12px] text-faint">No resolved graph links for this symbol.</p>
          )}
        </div>
      )}
    </section>
  );
}

function SymbolBrowser({
  analysisId,
  onSelect,
  selected,
}: {
  analysisId: number;
  onSelect: (name: string) => void;
  selected: string | null;
}) {
  const [filter, setFilter] = useState("");
  const symbols = useGraphSymbols(analysisId, "", true);
  const filtered = useMemo(() => {
    const all = symbols.data ?? [];
    if (!filter) return all.slice(0, 150);
    const needle = filter.toLowerCase();
    return all.filter((s: SymbolRef) => s.name.toLowerCase().includes(needle)).slice(0, 150);
  }, [symbols.data, filter]);

  return (
    <section className="panel p-5">
      <h4 className="text-[13px] font-semibold text-ink">Symbols</h4>
      <input
        value={filter}
        onChange={(event) => setFilter(event.target.value)}
        placeholder="Filter symbols…"
        className="input mt-2.5"
        aria-label="Filter symbols"
      />
      <ul className="scroll mt-2.5 max-h-96 space-y-1 overflow-y-auto pr-1">
        {filtered.map((symbol) => {
          const active = selected === symbol.name;
          return (
            <li key={symbol.id} className="card overflow-hidden">
              <button
                onClick={() => onSelect(symbol.name)}
                className={`flex w-full items-center gap-2 px-2.5 py-1.5 text-left text-[13px] transition-colors ${
                  active ? "bg-accent-soft" : "hover:bg-surface-2"
                }`}
              >
                <KindBadge kind={symbol.kind} />
                <span className="truncate font-mono text-ink/90">{symbol.name.split(".").pop()}</span>
                <span className="ml-auto shrink-0 text-[10px] text-faint">
                  {symbol.file_path.split("/").pop()}
                </span>
              </button>
            </li>
          );
        })}
      </ul>
      {symbols.data?.length === 0 && (
        <EmptyState
          title="No symbols"
          detail="This repository could not be indexed into a symbol graph."
        />
      )}
    </section>
  );
}

export function ExploreTab({ analysisId }: { analysisId: number }) {
  const summary = useGraphSummary(analysisId, true);
  const [selected, setSelected] = useState<string | null>(null);

  const symbolTotal = summary.data
    ? Object.values(summary.data.symbols).reduce((a, b) => a + b, 0)
    : null;
  const edgeTotal = summary.data
    ? Object.values(summary.data.edges).reduce((a, b) => a + b, 0)
    : null;

  return (
    <div className="space-y-6">
      <section className="panel p-5">
        <h3 className="text-[15px] font-semibold text-ink">Repository knowledge graph</h3>
        {summary.isLoading && <Loading label="Loading graph…" />}
        {summary.data && (
          <div className="mt-3.5 flex flex-wrap gap-2 text-[11px]">
            <span className="chip chip--flat border-line-strong bg-surface-2 text-ink tabular-nums">
              {symbolTotal} symbols
            </span>
            {Object.entries(summary.data.edges).map(([kind, count]) => (
              <span key={kind} className="chip chip--flat border-line bg-surface-2 text-muted tabular-nums">
                {count} {kind}
              </span>
            ))}
            <span className="chip chip--flat border-line bg-surface-2 text-muted tabular-nums">
              {edgeTotal} edges total
            </span>
          </div>
        )}
      </section>

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
        <SymbolBrowser analysisId={analysisId} onSelect={setSelected} selected={selected} />
        <NeighborhoodPanel analysisId={analysisId} root={selected} onSelect={setSelected} />
      </div>
    </div>
  );
}
