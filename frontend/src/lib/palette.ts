/**
 * One palette, one place.
 *
 * Before this module, PILLAR_LABELS was defined four times (ScoreHero,
 * FindingsTable, RemediationPlan, HistoryCompare), SEVERITY_STYLES three times
 * (FindingsTable, ApprovalQueue, RemediationPlan), and the score-threshold table
 * twice with *different* cutoffs. Three copies of a lookup that disagrees with
 * itself is how a palette drifts off-palette.
 *
 * Every value here has a light and a dark entry. Changing the dossier is a
 * values change, not a structure change: the shape of this module is stable
 * across redesigns.
 */

import type { Theme } from "./theme";

/** The theme shape lives in lib/theme.ts; re-exported here because palette.ts
    is the module every colour consumer already imports. */
export type { Theme };

export type Severity = "critical" | "high" | "medium" | "low" | "info";

export type Pillar =
  | "security"
  | "code-quality"
  | "testing"
  | "architecture"
  | "documentation"
  | "dependencies";

export type RunStatus = "pending" | "running" | "done" | "failed";

/** Canonical display order. ScoreHero renders these in this sequence. */
export const PILLARS: readonly Pillar[] = [
  "security",
  "code-quality",
  "testing",
  "architecture",
  "documentation",
  "dependencies",
];

export const PILLAR_LABELS: Record<Pillar, string> = {
  security: "Security",
  "code-quality": "Code quality",
  testing: "Testing",
  architecture: "Architecture",
  documentation: "Documentation",
  dependencies: "Dependencies",
};

/** The six pillars are one ink ladder: position and label carry the difference. */
const PILLAR_HEX: Record<Pillar, Record<Theme, string>> = {
  security: { dark: "#ece8e1", light: "#1d1a16" },
  "code-quality": { dark: "#c5bfb4", light: "#3d3830" },
  testing: { dark: "#9e978b", light: "#5d564c" },
  architecture: { dark: "#7a7469", light: "#7d766a" },
  documentation: { dark: "#585349", light: "#9d9689" },
  dependencies: { dark: "#3a3731", light: "#beb7aa" },
};

export const PILLAR_COLOR_VAR: Record<Pillar, string> = Object.fromEntries(
  PILLARS.map((pillar) => [pillar, `--pillar-${pillar}`]),
) as Record<Pillar, string>;

const SEVERITY_HEX: Record<Severity, Record<Theme, string>> = {
  critical: { dark: "#e06a5c", light: "#b0392c" },
  high: { dark: "#d99a3d", light: "#9a5b08" },
  medium: { dark: "#c2a04d", light: "#7a6a2a" },
  low: { dark: "#6f9ade", light: "#3568b8" },
  info: { dark: "#8d887e", light: "#6d6860" },
};

/** Warm means worse: red → orange → amber → blue → grey. */
export const SEVERITIES: readonly Severity[] = ["critical", "high", "medium", "low", "info"];

export const SEVERITY_COLOR_VAR: Record<Severity, string> = Object.fromEntries(
  SEVERITIES.map((severity) => [severity, `--sev-${severity}`]),
) as Record<Severity, string>;

const STATUS_HEX: Record<RunStatus, Record<Theme, string>> = {
  pending: { dark: "#8d887e", light: "#6d6860" },
  running: { dark: "#d99a3d", light: "#9a5b08" },
  done: { dark: "#4fb07d", light: "#1f7a4d" },
  failed: { dark: "#e06a5c", light: "#b0392c" },
};

export const STATUS_COLOR_VAR: Record<RunStatus, string> = Object.fromEntries(
  (["pending", "running", "done", "failed"] as const).map((status) => [
    status,
    `--status-${status}`,
  ]),
) as Record<RunStatus, string>;

export type Tone = "ok" | "info" | "warn" | "danger";

/**
 * The only score threshold table in the app. 80/60/40 — deliberately the same
 * table everywhere, including `ScoreHero`, which previously used 40 where the
 * dashboard used 50.
 */
export function scoreTone(score: number): Tone {
  if (score >= 80) return "ok";
  if (score >= 60) return "info";
  if (score >= 40) return "warn";
  return "danger";
}

/** The verdict in words, so a tone is never colour alone. One table, two
    surfaces: the analysis verdict stamp and the dashboard docket row. */
export const TONE_VERDICT_WORD: Record<Tone, string> = {
  ok: "healthy",
  info: "adequate",
  warn: "at risk",
  danger: "critical",
};

/**
 * Maps a `--pillar-*` / `--sev-*` / `--status-*` / tone reference to its two
 * themes. The four tone references are here too because the score gauge is the
 * one component that needs a literal, and it receives a tone, not a pillar.
 */
const BY_REF: Record<string, Record<Theme, string>> = {
  ...Object.fromEntries(
    PILLARS.map((pillar) => [`--pillar-${pillar}`, PILLAR_HEX[pillar]]),
  ),
  ...Object.fromEntries(
    SEVERITIES.map((severity) => [`--sev-${severity}`, SEVERITY_HEX[severity]]),
  ),
  "--status-pending": STATUS_HEX.pending,
  "--status-running": STATUS_HEX.running,
  "--status-done": STATUS_HEX.done,
  "--status-failed": STATUS_HEX.failed,
  "--ok": { dark: "#4fb07d", light: "#1f7a4d" },
  "--warn": { dark: "#d99a3d", light: "#9a5b08" },
  "--info": { dark: "#6f9ade", light: "#3568b8" },
  "--danger": { dark: "#e06a5c", light: "#b0392c" },
};

/**
 * Resolves `var(--name)` to a literal hex for `theme`. Components that paint into
 * SVG attributes cannot use CSS variables in a `fill` that also needs to be
 * read back. An unknown reference resolves to the canvas so a typo degrades to
 * background rather than to an invisible element.
 */
export function colorFor(reference: string, theme: Theme): string {
  const name = reference.replace(/^var\(/, "").replace(/\)$/, "").trim();
  const entry = BY_REF[name];
  return entry ? entry[theme] : theme === "dark" ? "#131210" : "#faf9f7";
}
