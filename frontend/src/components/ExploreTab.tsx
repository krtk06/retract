import { useMemo, useState } from "react";

import { useGraphSummary, useGraphSymbols, useNeighborhood } from "../api/hooks";
import type { GraphLink, SymbolRef } from "../api/types";

function KindBadge({ kind }: { kind: string }) {
  const colors: Record<string, string> = {
    module: "border-info/30 bg-info-soft text-info",
    class: "border-warn/30 bg-warn-soft text-warn",
    function: "border-ok/30 bg-ok-soft text-ok",
    method: "border-ok/30 bg-ok-soft text-ok",
  };
  return (
    <span
      className={`border px-1.5 py-0.5 text-[10px] font-semibold ${colors[kind] ?? "border-line bg-surface-2 text-muted"}`}
    >
      {kind}
    </span>
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
      <h5 className="px-eyebrow">{title}</h5>
      <ul className="mt-2 space-y-1">
        {links.map((link, index) => (
          <li key={index} className="flex items-center gap-2 text-sm">
            <button
              onClick={() => onSelect(link[field])}
              className="min-w-0 truncate text-left font-mono text-accent transition-colors duration-300 hover:underline"
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
    <section className="px-panel p-5">
      <h4 className="text-sm font-semibold text-ink">Dependency view</h4>
      {!root && <p className="mt-2 text-xs text-faint">Select a symbol to inspect its dependencies.</p>}
      {root && neighborhood.isLoading && <p className="mt-2 text-xs text-faint">Loading…</p>}
      {root && neighborhood.data && (
        <div className="mt-3 space-y-3">
          <p className="font-mono text-sm text-ink">
            {root}
            {neighborhood.data.root && (
              <span className="ml-2 text-xs text-faint">
                {neighborhood.data.root.file_path}:{neighborhood.data.root.line_start}
              </span>
            )}
          </p>
          <div className="grid grid-cols-1 gap-4">
            <LinkList title="Depends on" links={outgoing} field="target" onSelect={onSelect} />
            <LinkList title="Used by" links={incoming} field="source" onSelect={onSelect} />
          </div>
          {neighborhood.data.links.length === 0 && (
            <p className="text-xs text-faint">No resolved graph links for this symbol.</p>
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
    <section className="px-panel p-5">
      <h4 className="text-sm font-semibold text-ink">Symbols</h4>
      <input
        value={filter}
        onChange={(event) => setFilter(event.target.value)}
        placeholder="Filter symbols…"
        className="px-input mt-2.5 px-3 py-2 text-sm"
        aria-label="Filter symbols"
      />
      <ul className="mt-2.5 max-h-96 space-y-0.5 overflow-y-auto pr-1">
        {filtered.map((symbol) => (
          <li key={symbol.id}>
            <button
              onClick={() => onSelect(symbol.name)}
              className={`flex w-full items-center gap-2 px-2 py-1.5 text-left text-sm transition-colors duration-300 hover:bg-surface-2 ${
                selected === symbol.name ? "bg-accent-soft" : ""
              }`}
            >
              <KindBadge kind={symbol.kind} />
              <span className="truncate font-mono text-ink/90">{symbol.name.split(".").pop()}</span>
              <span className="ml-auto shrink-0 text-[10px] text-faint">
                {symbol.file_path.split("/").pop()}
              </span>
            </button>
          </li>
        ))}
      </ul>
      {symbols.data?.length === 0 && <p className="mt-2 text-xs text-faint">No symbols indexed.</p>}
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
      <section className="px-panel p-5">
        <h3 className="font-semibold text-ink">Repository Knowledge Graph</h3>
        {summary.isLoading && <p className="mt-2 text-xs text-faint">Loading graph…</p>}
        {summary.data && (
          <div className="mt-3.5 flex flex-wrap gap-2 text-xs">
            <span className="px-badge border border-line-strong bg-surface-2 text-ink tabular-nums">
              {symbolTotal} symbols
            </span>
            {Object.entries(summary.data.edges).map(([kind, count]) => (
              <span key={kind} className="px-badge border border-line bg-surface-2 text-muted tabular-nums">
                {count} {kind}
              </span>
            ))}
            <span className="px-badge border border-line bg-surface-2 text-muted tabular-nums">
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
