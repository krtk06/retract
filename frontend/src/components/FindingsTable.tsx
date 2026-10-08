import { useMemo, useState } from "react";

import { useSnippet } from "../api/hooks";
import type { Finding, Repository } from "../api/types";

const SEVERITY_STYLES: Record<Finding["severity"], string> = {
  critical: "bg-red-700 text-white",
  high: "bg-red-900 text-red-200",
  medium: "bg-amber-900 text-amber-200",
  low: "bg-sky-900 text-sky-200",
  info: "bg-zinc-700 text-zinc-300",
};

const PILLAR_BY_CATEGORY: Record<string, string> = {
  "code-smell": "code-quality",
  complexity: "code-quality",
  "complexity-review": "code-quality",
  maintainability: "code-quality",
  duplication: "code-quality",
  secret: "security",
  vulnerability: "security",
  injection: "security",
  "weak-crypto": "security",
  "vulnerable-dependency": "security",
  "missing-tests": "testing",
  coverage: "testing",
  "test-plan": "testing",
  readme: "documentation",
  docstring: "documentation",
  "docstring-plan": "documentation",
  "readme-plan": "documentation",
  "outdated-dependency": "dependencies",
  "import-cycle": "architecture",
  layering: "architecture",
  coupling: "architecture",
  "god-module": "architecture",
};

const PILLAR_LABELS: Record<string, string> = {
  "code-quality": "Code Quality",
  security: "Security",
  testing: "Testing",
  documentation: "Documentation",
  dependencies: "Dependencies",
  architecture: "Architecture",
};

const PILLAR_OPTIONS = [
  { value: "", label: "All pillars" },
  ...Object.entries(PILLAR_LABELS).map(([value, label]) => ({ value, label })),
];

const SEVERITY_OPTIONS = ["critical", "high", "medium", "low", "info"];

function StatusBadge({ status }: { status: Finding["status"] }) {
  if (status === "verified") {
    return (
      <span className="rounded bg-emerald-950 px-1.5 py-0.5 text-[10px] font-medium text-emerald-300">
        verified
      </span>
    );
  }
  if (status === "hypothesis") {
    return (
      <span className="rounded bg-purple-950 px-1.5 py-0.5 text-[10px] font-medium text-purple-300">
        hypothesis
      </span>
    );
  }
  return (
    <span className="rounded bg-zinc-800 px-1.5 py-0.5 text-[10px] text-zinc-400">dismissed</span>
  );
}

function FindingRow({
  finding,
  repository,
  commitSha,
  analysisId,
  showSnippet,
}: {
  finding: Finding;
  repository: Repository | null;
  commitSha: string | null;
  analysisId: number;
  showSnippet: boolean;
}) {
  const [expanded, setExpanded] = useState(false);
  const canSnippet = showSnippet && finding.file_path != null && finding.line_start != null;
  const snippet = useSnippet(
    analysisId,
    canSnippet && expanded ? finding.file_path : null,
    finding.line_start,
  );
  // The server derives this from the finding's category and evidence, so it costs
  // nothing extra. Optional because a stored payload from an older build has none.
  const fix = finding.remediation;

  const blobUrl =
    repository && !repository.url.startsWith("local://") && finding.file_path
      ? `${repository.url}/blob/${commitSha ?? repository.default_branch}/${finding.file_path}` +
        (finding.line_start ? `#L${finding.line_start}` : "")
      : null;

  return (
    <li className="rounded-lg border border-zinc-800 bg-zinc-900 px-4 py-3">
      <div className="flex flex-wrap items-center gap-2">
        <span
          className={`rounded px-1.5 py-0.5 text-[10px] font-semibold uppercase ${SEVERITY_STYLES[finding.severity]}`}
        >
          {finding.severity}
        </span>
        <p className="text-sm font-medium">{finding.title}</p>
        <StatusBadge status={finding.status} />
        <span className="ml-auto text-xs text-zinc-500">
          {finding.verifier} · conf {finding.confidence.toFixed(2)}
        </span>
      </div>
      {finding.description && (
        <p className="mt-1 text-sm text-zinc-400">{finding.description}</p>
      )}
      {fix && (
        <p className="mt-1 text-sm text-emerald-400/90">
          <span className="text-zinc-500">Fix:</span> {fix.action}
        </p>
      )}
      <div className="mt-1.5 flex flex-wrap items-center gap-3 text-xs">
        {finding.file_path && (
          <span className="font-mono text-zinc-500">
            {finding.file_path}
            {finding.line_start ? `:${finding.line_start}` : ""}
          </span>
        )}
        {blobUrl && (
          <a href={blobUrl} target="_blank" rel="noreferrer" className="text-sky-400 hover:underline">
            view on GitHub ↗
          </a>
        )}
        {canSnippet && (
          <button
            onClick={() => setExpanded((v) => !v)}
            className="text-zinc-400 hover:text-zinc-200"
          >
            {expanded ? "hide code" : "show code"}
          </button>
        )}
      </div>
      {expanded && canSnippet && (
        <div className="mt-2">
          {snippet.isLoading && <p className="text-xs text-zinc-500">Loading snippet…</p>}
          {snippet.data && (
            <pre className="overflow-x-auto rounded-md border border-zinc-800 bg-zinc-950 p-3 text-xs">
              {snippet.data.lines.map((line, i) => {
                const lineNo = snippet.data!.from_line + i;
                const isCited = lineNo === finding.line_start;
                return (
                  <div key={i} className={isCited ? "bg-amber-950/60" : ""}>
                    <span className="mr-3 select-none text-zinc-600">{lineNo}</span>
                    <span className="text-zinc-300">{line}</span>
                  </div>
                );
              })}
            </pre>
          )}
          {snippet.isError && (
            <p className="text-xs text-zinc-500">Snippet unavailable for this finding.</p>
          )}
        </div>
      )}
    </li>
  );
}

export function FindingsTable({
  findings,
  repository,
  commitSha,
  analysisId,
  groupByPillar = true,
}: {
  findings: Finding[];
  repository: Repository | null;
  commitSha: string | null;
  analysisId: number;
  groupByPillar?: boolean;
}) {
  const [pillarFilter, setPillarFilter] = useState("");
  const [severityFilter, setSeverityFilter] = useState("");
  const [hideMeta, setHideMeta] = useState(true);

  const filtered = useMemo(() => {
    return findings.filter((finding) => {
      if (hideMeta && (finding.category === "inventory" || finding.category === "tool-error")) {
        return false;
      }
      if (pillarFilter) {
        const pillar = PILLAR_BY_CATEGORY[finding.category] ?? "";
        if (pillar !== pillarFilter) return false;
      }
      if (severityFilter && finding.severity !== severityFilter) return false;
      return true;
    });
  }, [findings, pillarFilter, severityFilter, hideMeta]);

  const grouped = useMemo(() => {
    const map = new Map<string, Finding[]>();
    for (const finding of filtered) {
      const pillar = PILLAR_BY_CATEGORY[finding.category] ?? "other";
      if (!map.has(pillar)) map.set(pillar, []);
      map.get(pillar)!.push(finding);
    }
    return [...map.entries()].sort((a, b) => b[1].length - a[1].length);
  }, [filtered]);

  return (
    <section>
      <div className="mb-3 flex flex-wrap items-center justify-between gap-3">
        <h3 className="font-semibold">
          Findings <span className="text-sm text-zinc-500">({filtered.length})</span>
        </h3>
        <div className="flex flex-wrap gap-2 text-sm">
          <select
            value={pillarFilter}
            onChange={(e) => setPillarFilter(e.target.value)}
            className="rounded-md border border-zinc-700 bg-zinc-900 px-2 py-1 text-sm"
            aria-label="Filter by pillar"
          >
            {PILLAR_OPTIONS.map((o) => (
              <option key={o.value} value={o.value}>
                {o.label}
              </option>
            ))}
          </select>
          <select
            value={severityFilter}
            onChange={(e) => setSeverityFilter(e.target.value)}
            className="rounded-md border border-zinc-700 bg-zinc-900 px-2 py-1 text-sm"
            aria-label="Filter by severity"
          >
            <option value="">All severities</option>
            {SEVERITY_OPTIONS.map((s) => (
              <option key={s} value={s}>
                {s}
              </option>
            ))}
          </select>
          <label className="flex items-center gap-1.5 text-xs text-zinc-400">
            <input
              type="checkbox"
              checked={!hideMeta}
              onChange={(e) => setHideMeta(!e.target.checked)}
            />
            show ingestion
          </label>
        </div>
      </div>

      {filtered.length === 0 && (
        <p className="rounded-lg border border-zinc-800 bg-zinc-900 px-4 py-6 text-center text-sm text-zinc-500">
          No findings match the current filters.
        </p>
      )}

      {groupByPillar ? (
        <div className="space-y-6">
          {grouped.map(([pillar, items]) => (
            <div key={pillar}>
              <h4 className="mb-2 flex items-center gap-2 text-sm font-semibold text-zinc-300">
                {PILLAR_LABELS[pillar] ?? pillar}
                <span className="rounded-full bg-zinc-800 px-2 py-0.5 text-xs text-zinc-400">
                  {items.length}
                </span>
              </h4>
              <ul className="space-y-2">
                {items.map((finding) => (
                  <FindingRow
                    key={finding.id}
                    finding={finding}
                    repository={repository}
                    commitSha={commitSha}
                    analysisId={analysisId}
                    showSnippet
                  />
                ))}
              </ul>
            </div>
          ))}
        </div>
      ) : (
        <ul className="space-y-2">
          {filtered.map((finding) => (
            <FindingRow
              key={finding.id}
              finding={finding}
              repository={repository}
              commitSha={commitSha}
              analysisId={analysisId}
              showSnippet
            />
          ))}
        </ul>
      )}
    </section>
  );
}
