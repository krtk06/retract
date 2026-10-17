import { useMemo, useState } from "react";
import { useQueryClient } from "@tanstack/react-query";

import { copyText } from "../lib/clipboard";
import { buildFixPrompt } from "../lib/buildFixPrompt";
import { api } from "../api/client";
import { useSnippet } from "../api/hooks";
import type { Finding, Repository, SnippetResponse } from "../api/types";

const SEVERITY_STYLES: Record<Finding["severity"], string> = {
  critical: "border-danger/45 bg-danger-soft text-danger",
  high: "border-danger/25 bg-danger-soft text-danger",
  medium: "border-warn/30 bg-warn-soft text-warn",
  low: "border-info/25 bg-info-soft text-info",
  info: "border-line-strong bg-surface-2 text-muted",
};

const PILLAR_BY_CATEGORY: Record<string, string> = {
  "code-smell": "code-quality",
  complexity: "code-quality",
  "complexity-review": "code-quality",
  maintainability: "code-quality",
  duplication: "code-quality",
  secret: "security", // aislop-ignore-line security/hardcoded-secret -- finding-category key, not a credential
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
      <span className="border border-ok/30 bg-ok-soft px-1.5 py-0.5 text-[10px] font-semibold text-ok">
        verified
      </span>
    );
  }
  if (status === "hypothesis") {
    return (
      <span className="border border-hypo/30 bg-hypo-soft px-1.5 py-0.5 text-[10px] font-semibold text-hypo">
        hypothesis
      </span>
    );
  }
  return (
    <span className="border border-line bg-surface-2 px-1.5 py-0.5 text-[10px] font-medium text-muted">
      dismissed
    </span>
  );
}

function FixWithAgentButton({
  finding,
  repository,
  commitSha,
  analysisId,
  canSnippet,
}: {
  finding: Finding;
  repository: Repository | null;
  commitSha: string | null;
  analysisId: number;
  canSnippet: boolean;
}) {
  const queryClient = useQueryClient();
  const [copied, setCopied] = useState(false);

  // Retract dismissed this finding already: fixing it would be wrong, so the
  // button says nothing rather than handing the agent a false-positive brief.
  if (finding.status === "dismissed") {
    return (
      <span
        className="cursor-not-allowed text-faint/60"
        title="Dismissed as a false positive — do not fix"
      >
        fix with your agent
      </span>
    );
  }

  async function handleCopy() {
    // The snippet query is only enabled while the row is expanded, so prewarm
    // it here: by the time the user clicks, it is usually cached and the
    // clipboard text can include the cited region.
    if (canSnippet && finding.file_path != null && finding.line_start != null) {
      queryClient
        .fetchQuery({
          queryKey: ["snippet", analysisId, finding.file_path, finding.line_start],
          queryFn: () =>
            api.snippet(analysisId, finding.file_path as string, finding.line_start as number),
        })
        .catch(() => null);
    }
    const snippet =
      queryClient.getQueryData<SnippetResponse>([
        "snippet",
        analysisId,
        finding.file_path,
        finding.line_start,
      ]) ?? null;
    const text = buildFixPrompt({ finding, repository, commitSha, snippet });
    const ok = await copyText(text);
    setCopied(ok);
    if (ok) {
      window.setTimeout(() => setCopied(false), 2000);
    }
  }

  return (
    <button
      onClick={handleCopy}
      className={
        copied
          ? "px-btn border border-ok/40 px-2.5 py-1 text-xs text-ok"
          : "px-btn px-btn--ghost px-2.5 py-1 text-xs"
      }
      title="Copy a fix brief for your coding agent (opencode, Claude Code, Codex)"
    >
      {copied ? "Copied ✓" : "Fix with your agent"}
    </button>
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
    <li className="px-card px-card-hover px-4 py-3.5">
      <div className="flex flex-wrap items-center gap-2">
        <span
          className={`border px-1.5 py-0.5 text-[10px] font-bold uppercase tracking-wide ${SEVERITY_STYLES[finding.severity]}`}
        >
          {finding.severity}
        </span>
        <p className="text-sm font-semibold text-ink text-pretty">{finding.title}</p>
        <StatusBadge status={finding.status} />
        <span className="ml-auto text-xs text-faint tabular-nums">
          {finding.verifier} · conf {finding.confidence.toFixed(2)}
        </span>
      </div>
      {finding.description && (
        <p className="mt-1.5 text-sm leading-relaxed text-muted text-pretty">{finding.description}</p>
      )}
      {fix && (
        <p className="mt-1.5 text-sm text-ok/90 text-pretty">
          <span className="text-faint">Fix:</span> {fix.action}
        </p>
      )}
      <div className="mt-2.5 flex flex-wrap items-center gap-3 text-xs">
        {finding.file_path && (
          <span className="bg-surface-2 px-1.5 py-0.5 font-mono text-[11px] text-faint">
            {finding.file_path}
            {finding.line_start ? `:${finding.line_start}` : ""}
          </span>
        )}
        {blobUrl && (
          <a href={blobUrl} target="_blank" rel="noreferrer" className="px-link">
            view on GitHub ↗
          </a>
        )}
        {canSnippet && (
          <button onClick={() => setExpanded((v) => !v)} className="px-btn--quiet px-1.5 py-0.5">
            {expanded ? "hide code" : "show code"}
          </button>
        )}
        <FixWithAgentButton
          finding={finding}
          repository={repository}
          commitSha={commitSha}
          analysisId={analysisId}
          canSnippet={canSnippet}
        />
      </div>
      {expanded && canSnippet && (
        <div className="mt-2.5">
          {snippet.isLoading && <p className="text-xs text-faint">Loading snippet…</p>}
          {snippet.data && (
            <pre className="overflow-x-auto border border-line bg-surface-2 p-3 text-xs">
              {snippet.data.lines.map((line, i) => {
                const lineNo = snippet.data!.from_line + i;
                const isCited = lineNo === finding.line_start;
                return (
                  <div key={i} className={isCited ? "-mx-3 rounded bg-warn-soft px-3" : ""}>
                    <span className="mr-3 select-none text-faint/60 tabular-nums">{lineNo}</span>
                    <span className="text-ink/85">{line}</span>
                  </div>
                );
              })}
            </pre>
          )}
          {snippet.isError && (
            <p className="text-xs text-faint">Snippet unavailable for this finding.</p>
          )}
        </div>
      )}
    </li>
  );
}

function FindingList({
  findings,
  repository,
  commitSha,
  analysisId,
}: {
  findings: Finding[];
  repository: Repository | null;
  commitSha: string | null;
  analysisId: number;
}) {
  return (
    <ul className="space-y-2.5">
      {findings.map((finding) => (
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
    <section className="px-panel p-5 sm:p-6">
      <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
        <h3 className="font-semibold text-ink">
          Findings <span className="text-sm font-normal text-faint tabular-nums">({filtered.length})</span>
        </h3>
        <div className="flex flex-wrap items-center gap-2 text-sm">
          <select
            value={pillarFilter}
            onChange={(e) => setPillarFilter(e.target.value)}
            className="px-input px-select w-auto px-2.5 py-1.5 text-xs"
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
            className="px-input px-select w-auto px-2.5 py-1.5 text-xs"
            aria-label="Filter by severity"
          >
            <option value="">All severities</option>
            {SEVERITY_OPTIONS.map((s) => (
              <option key={s} value={s}>
                {s}
              </option>
            ))}
          </select>
          <label className="flex cursor-pointer items-center gap-2 border border-line bg-surface-2 px-3 py-1.5 text-xs text-muted transition-colors duration-300 hover:text-ink">
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
        <p className="border border-line bg-surface-2 px-4 py-8 text-center text-sm text-faint">
          No findings match the current filters.
        </p>
      )}

      {groupByPillar ? (
        <div className="space-y-7">
          {grouped.map(([pillar, items]) => (
            <div key={pillar}>
              <h4 className="mb-3 flex items-center gap-2 text-sm font-semibold text-ink">
                {PILLAR_LABELS[pillar] ?? pillar}
                <span className="bg-surface-2 px-2 py-0.5 text-xs text-muted tabular-nums">
                  {items.length}
                </span>
              </h4>
              <FindingList
                findings={items}
                repository={repository}
                commitSha={commitSha}
                analysisId={analysisId}
              />
            </div>
          ))}
        </div>
      ) : (
        <FindingList
          findings={filtered}
          repository={repository}
          commitSha={commitSha}
          analysisId={analysisId}
        />
      )}
    </section>
  );
}
