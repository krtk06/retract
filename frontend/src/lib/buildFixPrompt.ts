import type { Finding, Repository, SnippetResponse } from "../api/types";

const INSTALL_COMMAND = "npx skills add krtk06/retract --skill retract";

// The hand-off prompt the "Fix with your agent" button puts on the clipboard.
// Everything the user's coding agent needs must be in this text: it runs on
// their machine, with no session cookie for this app and no way to query it.
const EVIDENCE_LIMIT = 4000;
const SNIPPET_LINE_LIMIT = 40;

export function buildFixPrompt(input: {
  finding: Finding;
  repository: Repository | null;
  commitSha: string | null;
  snippet: SnippetResponse | null;
}): string {
  const { finding, repository, commitSha, snippet } = input;
  const lines: string[] = [];

  lines.push("# Retract");
  lines.push("");
  lines.push("If the retract skill is not installed:");
  lines.push(`  ${INSTALL_COMMAND}`);
  lines.push("");
  lines.push(
    "Use the retract skill to resolve this finding. When you are done, tell me to push and re-analyze so I can see the score move.",
  );
  lines.push("");
  lines.push("## Instruction");
  lines.push(finding.remediation?.action ?? finding.title);
  lines.push("");
  lines.push("## Finding");

  const repo = repository ? `${repository.owner}/${repository.name}` : null;
  const header = [
    repo ? `Retract analysis #${finding.analysis_id} of ${repo}` : `Retract analysis #${finding.analysis_id}`,
    commitSha ? `@ ${commitSha.slice(0, 12)}` : null,
  ]
    .filter(Boolean)
    .join(" ");
  lines.push(header);

  const pillar = PILLAR_BY_CATEGORY[finding.category];
  lines.push(
    [
      `finding_id: ${finding.id}`,
      `category: ${finding.category}`,
      pillar ? `pillar: ${pillar}` : null,
      `severity: ${finding.severity}`,
      `status: ${finding.status}`,
      `confidence: ${finding.confidence.toFixed(2)}`,
      `verifier: ${finding.verifier}`,
      `agent: ${finding.agent}`,
    ]
      .filter(Boolean)
      .join(" · "),
  );

  if (finding.remediation) {
    lines.push(`effort: ${finding.remediation.effort} · source: ${finding.remediation.source}`);
  }

  lines.push("");
  lines.push(`Title: ${finding.title}`);
  if (finding.description) {
    lines.push("");
    lines.push(finding.description);
  }

  if (finding.file_path) {
    lines.push("");
    const location = finding.line_end
      ? `${finding.file_path}:${finding.line_start}-${finding.line_end}`
      : `${finding.file_path}:${finding.line_start ?? "?"}`;
    lines.push(`Cited location: ${location}`);
    if (snippet) {
      lines.push("");
      lines.push("```");
      const truncated = snippet.lines.slice(0, SNIPPET_LINE_LIMIT);
      for (const [index, line] of truncated.entries()) {
        lines.push(`${snippet.from_line + index}\t${line}`);
      }
      if (snippet.lines.length > SNIPPET_LINE_LIMIT) {
        lines.push("… snippet truncated");
      }
      lines.push("```");
    }
  }

  if (finding.evidence_json && Object.keys(finding.evidence_json).length > 0) {
    lines.push("");
    lines.push("Evidence:");
    lines.push("```json");
    let evidence = JSON.stringify(finding.evidence_json, null, 2);
    if (evidence.length > EVIDENCE_LIMIT) {
      evidence = `${evidence.slice(0, EVIDENCE_LIMIT)}\n… evidence truncated`;
    }
    lines.push(evidence);
    lines.push("```");
  }

  return lines.join("\n");
}

// Kept in sync with the server's CATEGORY_PILLAR map; the pillar is derived,
// never stored, so the client needs the same table.
export const PILLAR_BY_CATEGORY: Record<string, string> = {
  "code-smell": "code-quality",
  complexity: "code-quality",
  maintainability: "code-quality",
  duplication: "code-quality",
  secret: "security",
  vulnerability: "security",
  injection: "security",
  "weak-crypto": "security",
  "vulnerable-dependency": "security",
  "missing-tests": "testing",
  coverage: "testing",
  readme: "documentation",
  docstring: "documentation",
  "outdated-dependency": "dependencies",
  "import-cycle": "architecture",
  "god-module": "architecture",
};
