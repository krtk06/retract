/**
 * One palette, one place.
 *
 * Before this module, PILLAR_LABELS was defined four times (ScoreHero,
 * FindingsTable, RemediationPlan, HistoryCompare), SEVERITY_STYLES three times
 * (FindingsTable, ApprovalQueue, RemediationPlan), and the score-threshold table
 * twice with *different* cutoffs — DashboardPage broke at 50 where ScoreHero broke
 * at 40, so the same score rendered in two colours. Three copies of a lookup that
 * disagrees with itself is how a palette drifts off-palette.
 *
 * Every colour here is one of the 16 canonical PICO-8 entries. Nothing else.
 */

export type Theme = "dark" | "light";

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

/** Light mode has no yellow that survives on cream, so its ramp steps through
 *  brown → purple rather than orange → yellow. Warmth still increases with
 *  severity, which is the property carrying the meaning. */
const PILLAR_HEX: Record<Pillar, Record<Theme, string>> = {
  security: { dark: "#FF004D", light: "#FF004D" },
  "code-quality": { dark: "#FFA300", light: "#AB5236" },
  testing: { dark: "#29ADFF", light: "#1D2B53" },
  architecture: { dark: "#83769C", light: "#7E2553" },
  documentation: { dark: "#FF77A8", light: "#008751" },
  dependencies: { dark: "#00E436", light: "#5F574F" },
};

export const PILLAR_COLOR_VAR: Record<Pillar, string> = Object.fromEntries(
  PILLARS.map((pillar) => [pillar, `--pillar-${pillar}`]),
) as Record<Pillar, string>;

const SEVERITY_HEX: Record<Severity, Record<Theme, string>> = {
  critical: { dark: "#FF004D", light: "#FF004D" },
  high: { dark: "#FFA300", light: "#AB5236" },
  medium: { dark: "#FFEC27", light: "#7E2553" },
  low: { dark: "#29ADFF", light: "#1D2B53" },
  info: { dark: "#C2C3C7", light: "#5F574F" },
};

/** Warm means worse: red → orange → yellow → blue → grey. */
export const SEVERITIES: readonly Severity[] = ["critical", "high", "medium", "low", "info"];

export const SEVERITY_COLOR_VAR: Record<Severity, string> = Object.fromEntries(
  SEVERITIES.map((severity) => [severity, `--sev-${severity}`]),
) as Record<Severity, string>;

const STATUS_HEX: Record<RunStatus, Record<Theme, string>> = {
  pending: { dark: "#83769C", light: "#5F574F" },
  running: { dark: "#FFEC27", light: "#AB5236" },
  done: { dark: "#00E436", light: "#008751" },
  failed: { dark: "#FF004D", light: "#FF004D" },
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

/**
 * Maps a `--pillar-*` / `--sev-*` / `--status-*` / tone reference to its two
 * themes. The four tone references are here too because ScoreRing is the one
 * component that needs a literal, and it receives a tone, not a pillar.
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
  "--ok": { dark: "#00E436", light: "#008751" },
  "--warn": { dark: "#FFA300", light: "#AB5236" },
  "--info": { dark: "#FFEC27", light: "#1D2B53" },
  "--danger": { dark: "#FF004D", light: "#FF004D" },
};

/**
 * Resolves `var(--name)` to a literal hex for `theme`. Components that paint into
 * SVG attributes cannot use CSS variables in a `fill` that also needs to be
 * read back, and `<animate>`-style gradients need the value at build time.
 * An unknown reference resolves to the canvas so a typo degrades to background
 * rather than to an invisible element.
 */
export function colorFor(reference: string, theme: Theme): string {
  const name = reference.replace(/^var\(/, "").replace(/\)$/, "").trim();
  const entry = BY_REF[name];
  return entry ? entry[theme] : theme === "dark" ? "#000000" : "#C2C3C7";
}
