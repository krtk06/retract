import { useMemo, useState } from "react";

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
  maintainability: "code-quality",
  duplication: "code-quality",
  secret: "security",
  vulnerability: "security",
  "vulnerable-dependency": "security",
  "missing-tests": "testing",
  coverage: "testing",
  readme: "documentation",
  docstring: "documentation",
  "outdated-dependency": "dependencies",
  "import-cycle": "architecture",
  "god-module": "architecture",
  inventory: "",
  "tool-error": "",
};

const PILLAR_OPTIONS = [
  { value: "", label: "All pillars" },
  { value: "code-quality", label: "Code Quality" },
  { value: "security", label: "Security" },
  { value: "testing", label: "Testing" },
  { value: "documentation", label: "Documentation" },
  { value: "dependencies", label: "Dependencies" },
  { value: "architecture", label: "Architecture" },
];

const SEVERITY_OPTIONS = ["all", "critical", "high", "medium", "low", "info"];

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

export function FindingsTable({
  findings,
  repository,
  commitSha,
}: {
  findings: Finding[];
  repository: Repository | null;
  commitSha: string | null;
}) {
  const [pillarFilter, setPillarFilter] = useState("");
  const [severityFilter, setSeverityFilter] = useState("");
  const [hideInventory, setHideInventory] = useState(true);

  const filtered = useMemo(() => {
    return findings.filter((finding) => {
      if (hideInventory && (finding.category === "inventory" || finding.category === "tool-error")) {
        return false;
      }
      if (pillarFilter) {
        const pillar = PILLAR_BY_CATEGORY[finding.category] ?? "";
        if (pillar !== pillarFilter) return false;
      }
      if (severityFilter && finding.severity !== severityFilter) return false;
      return true;
    });
  }, [findings, pillarFilter, severityFilter, hideInventory]);

  function citationUrl(finding: Finding): string | null {
    if (!finding.file_path || !repository) return null;
    if (repository.url.startsWith("local://")) return null;
    const base = `${repository.url}/blob/${commitSha ?? repository.default_branch}`;
    return finding.line_start
      ? `${base}/${finding.file_path}#L${finding.line_start}`
      : `${base}/${finding.file_path}`;
  }

  return (
    <section>
      <div className="mb-3 flex flex-wrap items-center justify-between gap-3">
        <h3 className="font-semibold">
          Findings <span className="text-sm text-zinc-500">({filtered.length})</span>
        </h3>
        <div className="flex gap-2 text-sm">
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
            className="rounded border border-zinc-700 bg-zinc-900 px-2 py-1 text-sm"
            aria-label="Filter by severity"
          >
            <option value="">All severities</option>
            {SEVERITY_OPTIONS.slice(1).map((s) => (
              <option key={s} value={s}>
                {s}
              </option>
            ))}
          </select>
          <label className="flex items-center gap-1.5 text-xs text-zinc-400">
            <input
              type="checkbox"
              checked={!hideInventory}
              onChange={(e) => setHideInventory(!e.target.checked)}
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

      <ul className="space-y-2">
        {filtered.map((finding) => {
          const url = citationUrl(finding);
          return (
            <li
              key={finding.id}
              className="rounded-lg border border-zinc-800 bg-zinc-900 px-4 py-3"
            >
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
              <div className="mt-1.5 flex items-center gap-3 text-xs">
                {finding.file_path && (
                  <span className="font-mono text-zinc-500">
                    {finding.file_path}
                    {finding.line_start ? `:${finding.line_start}` : ""}
                  </span>
                )}
                {url && (
                  <a
                    href={url}
                    target="_blank"
                    rel="noreferrer"
                    className="text-sky-400 hover:underline"
                  >
                    view on GitHub ↗
                  </a>
                )}
              </div>
            </li>
          );
        })}
      </ul>
    </section>
  );
}
