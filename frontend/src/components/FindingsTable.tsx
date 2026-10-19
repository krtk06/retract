import { useMemo, useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { m } from "motion/react";

import { copyText } from "../lib/clipboard";
import { buildFixPrompt } from "../lib/buildFixPrompt";
import { api } from "../api/client";
import { useSnippet } from "../api/hooks";
import { EASE, stagger } from "../lib/motion";
import {
  PILLARS,
  PILLAR_LABELS,
  SEVERITIES,
  SEVERITY_COLOR_VAR,
  type Pillar,
} from "../lib/palette";
import { Icon } from "./Icon";
import { EmptyState } from "./EmptyState";
import type { Finding, Repository, SnippetResponse } from "../api/types";

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

const PILLAR_OPTIONS = [
  { value: "", label: "All pillars" },
  ...PILLARS.map((pillar) => ({ value: pillar, label: PILLAR_LABELS[pillar] })),
];

const SEVERITY_OPTIONS = SEVERITIES;

function StatusBadge({ status }: { status: Finding["status"] }) {
  if (status === "verified") {
    return <span className="chip border-ok/40 bg-ok-soft text-ok">verified</span>;
  }
  if (status === "hypothesis") {
    return <span className="chip border-hypo/40 bg-hypo-soft text-hypo">hypothesis</span>;
  }
  return <span className="chip border-line bg-surface-2 text-muted">dismissed</span>;
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
      className={copied ? "btn btn--ghost" : "btn btn--primary sheen press"}
      title="Copy a fix brief for your coding agent (opencode, Claude Code, Codex)"
    >
      {copied ? (
        <>
          <m.span
            className="grid place-items-center"
            initial={{ scale: 0.6, opacity: 0 }}
            animate={{ scale: 1, opacity: 1 }}
            transition={{ duration: 0.22, ease: EASE }}
          >
            <Icon name="check" size={15} />
          </m.span>
          <span>Copied ✓</span>
        </>
      ) : (
        "Fix with your agent"
      )}
    </button>
  );
}

function FindingRow({
  finding,
  repository,
  commitSha,
  analysisId,
  showSnippet,
  striped = false,
  index = 0,
}: {
  finding: Finding;
  repository: Repository | null;
  commitSha: string | null;
  analysisId: number;
  showSnippet: boolean;
  striped?: boolean;
  index?: number;
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

  const severityColor = `var(${SEVERITY_COLOR_VAR[finding.severity]})`;

  // Only the head of a long ledger is staggered; the tail arrives as one quiet
  // block, or a 191-row list would spend seconds entering.
  const appendDelay = stagger(index, 0.035, 0.28);

  const blobUrl =
    repository && !repository.url.startsWith("local://") && finding.file_path
      ? `${repository.url}/blob/${commitSha ?? repository.default_branch}/${finding.file_path}` +
        (finding.line_start ? `#L${finding.line_start}` : "")
      : null;

  return (
    <m.li
      layout
      initial={{ opacity: 0, y: 5 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.34, ease: EASE, delay: appendDelay }}
      className={`card card--hover px-4 py-3.5 ${striped ? "stripes" : ""}`}
    >
      <div className="flex flex-wrap items-center gap-2">
        <span
          className="chip chip--flat"
          style={{ borderColor: severityColor, color: severityColor }}
        >
          {finding.severity}
        </span>
        <p className="text-[13px] font-medium text-ink text-pretty">{finding.title}</p>
        <StatusBadge status={finding.status} />
        <span className="ml-auto text-[11px] text-faint tabular-nums">
          {finding.verifier} · conf {finding.confidence.toFixed(2)}
        </span>
      </div>
      {finding.description && (
        <p className="mt-1.5 text-[13px] leading-relaxed text-muted text-pretty">
          {finding.description}
        </p>
      )}
      {fix && (
        <p className="mt-1.5 text-[13px] text-ok/90 text-pretty">
          <span className="text-faint">Fix:</span> {fix.action}
        </p>
      )}
      <div className="mt-2.5 flex flex-wrap items-center gap-3 text-[12px]">
        {finding.file_path && (
          <span className="rounded-[2px] bg-surface-2 px-1.5 py-0.5 font-mono text-[11px] text-muted">
            {finding.file_path}
            {finding.line_start ? `:${finding.line_start}` : ""}
          </span>
        )}
        {blobUrl && (
          <a href={blobUrl} target="_blank" rel="noreferrer" className="link inline-flex items-center gap-1">
            view on GitHub
            <Icon name="external" size={12} />
          </a>
        )}
        {canSnippet && (
          <button onClick={() => setExpanded((v) => !v)} className="btn btn--quiet">
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
        <m.div
          className="mt-2.5 overflow-hidden"
          initial={{ opacity: 0, height: 0 }}
          animate={{ opacity: 1, height: "auto" }}
          transition={{ duration: 0.26, ease: EASE }}
        >
          {snippet.isLoading && <p className="text-[12px] text-faint">Loading snippet…</p>}
          {snippet.data && (
            <pre className="scroll overflow-x-auto rounded-[2px] border border-line bg-surface-2 p-3 text-[12px]">
              {snippet.data.lines.map((line, i) => {
                const lineNo = snippet.data!.from_line + i;
                const isCited = lineNo === finding.line_start;
                return (
                  <div key={i} className={isCited ? "-mx-3 rounded-[4px] bg-warn-soft px-3" : ""}>
                    <span className="mr-3 select-none text-faint/60 tabular-nums">{lineNo}</span>
                    <span className="text-ink/85">{line}</span>
                  </div>
                );
              })}
            </pre>
          )}
          {snippet.isError && (
            <p className="text-[12px] text-faint">Snippet unavailable for this finding.</p>
          )}
        </m.div>
      )}
    </m.li>
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
    <ul className="scroll space-y-2.5 overflow-x-auto">
      {findings.map((finding, index) => (
        <FindingRow
          key={finding.id}
          finding={finding}
          repository={repository}
          commitSha={commitSha}
          analysisId={analysisId}
          showSnippet
          striped={index % 2 === 1}
          index={index}
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
    <section className="panel p-6">
      <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
        <h3 className="text-[15px] font-semibold text-ink">
          Findings{" "}
          <span className="text-[13px] font-normal text-faint tabular-nums">
            ({filtered.length})
          </span>
        </h3>
        <div className="flex flex-wrap items-center gap-2 text-[13px]">
          <span className="select-wrap">
            <select
              value={pillarFilter}
              onChange={(e) => setPillarFilter(e.target.value)}
              className="input select w-auto"
              aria-label="Filter by pillar"
            >
              {PILLAR_OPTIONS.map((o) => (
                <option key={o.value} value={o.value}>
                  {o.label}
                </option>
              ))}
            </select>
            <Icon name="chevron-down" size={15} className="select-chevron" />
          </span>
          <span className="select-wrap">
            <select
              value={severityFilter}
              onChange={(e) => setSeverityFilter(e.target.value)}
              className="input select w-auto"
              aria-label="Filter by severity"
            >
              <option value="">All severities</option>
              {SEVERITY_OPTIONS.map((s) => (
                <option key={s} value={s}>
                  {s}
                </option>
              ))}
            </select>
            <Icon name="chevron-down" size={15} className="select-chevron" />
          </span>
          <label className="flex cursor-pointer items-center gap-2 rounded-[2px] border border-line bg-surface-2 px-3 py-1.5 text-[12px] text-muted transition-colors hover:text-ink">
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
        <EmptyState
          title="No findings match"
          detail="Loosen the filter, or pick another pillar."
        />
      )}

      {groupByPillar ? (
        <div className="space-y-7">
          {grouped.map(([pillar, items]) => (
            <div key={pillar}>
              <h4 className="mb-3 flex items-center gap-2 text-[13px] font-semibold text-ink">
                {PILLAR_LABELS[pillar as Pillar] ?? pillar}
                <span className="chip chip--flat text-muted tabular-nums">{items.length}</span>
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
