import { describe, expect, it } from "vitest";

import { buildFixPrompt } from "../lib/buildFixPrompt";
import type { Finding, Repository, SnippetResponse } from "../api/types";

const repository: Repository = {
  id: 1,
  owner: "krtk06",
  name: "seedy-python-app",
  url: "https://github.com/krtk06/seedy-python-app",
  default_branch: "main",
  created_at: "2026-10-01T00:00:00Z",
  latest_analysis_id: 18,
  latest_analysis_status: "done",
};

const finding: Finding = {
  id: 42,
  analysis_id: 18,
  agent: "tool:semgrep",
  category: "injection",
  severity: "high",
  title: "SQL query built with an f-string",
  description: "find_user() interpolates the caller-controlled name into the query text.",
  file_path: "app/db.py",
  line_start: 8,
  line_end: 12,
  evidence_json: { rule: "python.sqlalchemy.sqli", claim: "f-string query" },
  verifier: "verified:source-pattern",
  confidence: 0.9,
  status: "verified",
  created_at: "2026-10-08T00:00:00Z",
  remediation: { action: "Use parameterised queries instead of building SQL with an f-string", effort: "low", source: "catalog" },
};

const snippet: SnippetResponse = {
  path: "app/db.py",
  line_start: 8,
  from_line: 6,
  to_line: 12,
  lines: ["", "def find_user(name):", "    cur = conn.cursor()", '    cur.execute(f"SELECT * FROM users WHERE name = \'{name}\'")'],
};

describe("buildFixPrompt", () => {
  const build = (overrides: Partial<{ snippet: SnippetResponse | null; repository: Repository | null; finding: Finding }> = {}) =>
    buildFixPrompt({
      finding,
      repository,
      commitSha: "abc123def4567890",
      snippet: snippet,
      ...overrides,
    });

  it("leads with the install command and the skill invocation", () => {
    const text = build();
    expect(text).toContain("# Retract");
    expect(text).toContain("npx skills add krtk06/retract --skill retract");
    expect(text).toContain("Use the retract skill to resolve this finding");
    // The loop's exit: the agent must hand back the re-score step.
    expect(text).toContain("push and re-analyze");
  });

  it("carries the instruction, the finding's identity, and the citation", () => {
    const text = build();
    expect(text).toContain("## Instruction");
    expect(text).toContain("Use parameterised queries instead of building SQL with an f-string");
    expect(text).toContain("Retract analysis #18 of krtk06/seedy-python-app @ abc123def456");
    expect(text).toContain("finding_id: 42 · category: injection · pillar: security");
    expect(text).toContain("severity: high · status: verified");
    expect(text).toContain("Cited location: app/db.py:8-12");
  });

  it("includes the snippet with its true line numbers", () => {
    const text = build();
    expect(text).toContain("6\t");
    expect(text).toContain("cur.execute(");
  });

  it("includes the evidence as JSON", () => {
    const text = build();
    expect(text).toContain("Evidence:");
    expect(text).toContain('"rule": "python.sqlalchemy.sqli"');
  });

  it("omits the snippet when none was cached", () => {
    const text = build({ snippet: null });
    expect(text).toContain("Cited location: app/db.py:8-12");
    expect(text).not.toContain("cur.execute(");
  });

  it("degrades without a repository or a remediation", () => {
    const text = buildFixPrompt({
      finding: { ...finding, remediation: undefined },
      repository: null,
      commitSha: null,
      snippet: null,
    });
    expect(text).toContain("Retract analysis #18");
    // No remediation stored: the title is the instruction rather than nothing.
    expect(text).toContain("SQL query built with an f-string");
    expect(text).not.toContain("effort:");
  });

  it("truncates oversized evidence instead of pasting megabytes", () => {
    const huge: Finding = {
      ...finding,
      evidence_json: { blob: "x".repeat(6000) },
    };
    const text = buildFixPrompt({ finding: huge, repository, commitSha: null, snippet: null });
    expect(text).toContain("… evidence truncated");
    expect(text.length).toBeLessThan(7000);
  });
});
