import { useMemo, useState } from "react";

import { useGraphSummary, useGraphSymbols, useNeighborhood } from "../api/hooks";
import type { GraphLink, SymbolRef } from "../api/types";

function KindBadge({ kind }: { kind: string }) {
  const colors: Record<string, string> = {
    module: "bg-sky-950 text-sky-300",
    class: "bg-amber-950 text-amber-300",
    function: "bg-emerald-950 text-emerald-300",
    method: "bg-emerald-950 text-emerald-300",
  };
  return (
    <span className={`rounded px-1.5 py-0.5 text-[10px] font-medium ${colors[kind] ?? "bg-zinc-800 text-zinc-300"}`}>
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
      <h5 className="text-xs font-semibold uppercase tracking-wide text-zinc-500">{title}</h5>
      <ul className="mt-1.5 space-y-1">
        {links.map((link, index) => (
          <li key={index} className="flex items-center gap-2 text-sm">
            <button
              onClick={() => onSelect(link[field])}
              className="min-w-0 truncate text-left font-mono text-sky-400 hover:underline"
              title={link[field]}
            >
              {link[field]}
            </button>
            <span className="ml-auto shrink-0 text-[10px] uppercase text-zinc-600">
              {link.kind}
            </span>
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
    <section className="rounded-lg border border-zinc-800 bg-zinc-900 p-4">
      <h4 className="text-sm font-semibold">Dependency view</h4>
      {!root && <p className="mt-2 text-xs text-zinc-500">Select a symbol to inspect its dependencies.</p>}
      {root && neighborhood.isLoading && <p className="mt-2 text-xs text-zinc-500">Loading…</p>}
      {root && neighborhood.data && (
        <div className="mt-3 space-y-3">
          <p className="font-mono text-sm">
            {root}
            {neighborhood.data.root && (
              <span className="ml-2 text-xs text-zinc-500">
                {neighborhood.data.root.file_path}:{neighborhood.data.root.line_start}
              </span>
            )}
          </p>
          <div className="grid grid-cols-1 gap-4">
            <LinkList title="Depends on" links={outgoing} field="target" onSelect={onSelect} />
            <LinkList title="Used by" links={incoming} field="source" onSelect={onSelect} />
          </div>
          {neighborhood.data.links.length === 0 && (
            <p className="text-xs text-zinc-500">No resolved graph links for this symbol.</p>
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
    <section className="rounded-lg border border-zinc-800 bg-zinc-900 p-4">
      <h4 className="text-sm font-semibold">Symbols</h4>
      <input
        value={filter}
        onChange={(event) => setFilter(event.target.value)}
        placeholder="Filter symbols…"
        className="mt-2 w-full rounded-md border border-zinc-700 bg-zinc-950 px-3 py-1.5 text-sm outline-none placeholder:text-zinc-600 focus:border-zinc-500"
        aria-label="Filter symbols"
      />
      <ul className="mt-2 max-h-96 space-y-0.5 overflow-y-auto">
        {filtered.map((symbol) => (
          <li key={symbol.id}>
            <button
              onClick={() => onSelect(symbol.name)}
              className={`flex w-full items-center gap-2 rounded px-2 py-1 text-left text-sm hover:bg-zinc-800 ${
                selected === symbol.name ? "bg-zinc-800" : ""
              }`}
            >
              <KindBadge kind={symbol.kind} />
              <span className="truncate font-mono">{symbol.name.split(".").pop()}</span>
              <span className="ml-auto shrink-0 text-[10px] text-zinc-600">
                {symbol.file_path.split("/").pop()}
              </span>
            </button>
          </li>
        ))}
      </ul>
      {symbols.data?.length === 0 && <p className="mt-2 text-xs text-zinc-500">No symbols indexed.</p>}
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
    <div className="space-y-5">
      <section className="rounded-lg border border-zinc-800 bg-zinc-900 p-4">
        <h3 className="font-semibold">Repository Knowledge Graph</h3>
        {summary.isLoading && <p className="mt-2 text-xs text-zinc-500">Loading graph…</p>}
        {summary.data && (
          <div className="mt-3 flex flex-wrap gap-2 text-xs">
            <span className="rounded-full bg-zinc-800 px-2.5 py-1">{symbolTotal} symbols</span>
            {Object.entries(summary.data.edges).map(([kind, count]) => (
              <span key={kind} className="rounded-full bg-zinc-800 px-2.5 py-1">
                {count} {kind}
              </span>
            ))}
            <span className="rounded-full bg-zinc-800 px-2.5 py-1">{edgeTotal} edges total</span>
          </div>
        )}
      </section>

      <div className="grid grid-cols-1 gap-5 lg:grid-cols-2">
        <SymbolBrowser analysisId={analysisId} onSelect={setSelected} selected={selected} />
        <NeighborhoodPanel analysisId={analysisId} root={selected} onSelect={setSelected} />
      </div>
    </div>
  );
}
