# Pixel UI Redesign Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the emerald "aurora glass" UI with a hard-edged PICO-8 pixel system — new tokens, new primitives, a window-chrome + sidebar shell, and every page and component restyled.

**Architecture:** The design system stays CSS-first (Tailwind v4 `@theme inline` behind CSS variables) so all 21 color utilities keep resolving from `:root` / `.dark`. Three new modules extract what is currently duplicated across the codebase — `lib/palette.ts` (severity/pillar/status color and thresholds), `components/PixelIcon.tsx` (grid-string icons), `components/Meter.tsx` (the 20-cell meter and score ring). Everything else is a class migration plus per-screen structural work.

**Tech Stack:** React 18.3, TypeScript 5.6 strict, Vite 5.4, Tailwind v4.1 (CSS-first), Vitest + Testing Library. No new npm dependencies. Three Google Fonts: Silkscreen, Pixelify Sans, JetBrains Mono.

**Spec:** `docs/superpowers/specs/2026-10-17-pixel-ui-redesign-design.md`

---

## Global Constraints

These apply to every task. Do not deviate without checking the spec.

1. **Only the 16 PICO-8 colours appear as literal hex values.** Canonical set:
   `#000000 #1D2B53 #7E2553 #008751 #AB5236 #5F574F #C2C3C7 #FFF1E8 #FF004D #FFA300 #FFEC27 #00E436 #29ADFF #83769C #FF77A8 #FFCCAA`.
   The only permitted non-palette values are `--bevel-hi`, `--bevel-lo`, and the opacity/alpha derivations listed in Task 4.
2. **No `border-radius` anywhere.** Task 4 installs a global `* { border-radius: 0 }` reset. Never write `rounded-*`.
3. **No `backdrop-filter`, no `blur()`, no colour gradients, no soft/box shadows.** Depth comes from fill swap + bevel + hard offset shadow only.
4. **Silkscreen never renders prose.** UI atoms and numbers only. Body text is Pixelify Sans at 13px minimum.
5. **No new user-visible strings where a test pins one.** The pinned list is in the spec §9. When a label must change, change the test in the same commit.
6. **No new npm dependencies.** Google Fonts are a `<link>` in `index.html`, nothing more.
7. **Verification per task is always all four:** `npm run lint && npm run typecheck && npm test && npm run build` from `frontend/`.
8. **Commit after every task.** Messages follow the repo's imperative style: `feat - `, `fix - `, `chore - `, `docs - ` (note the space-hyphen-space, matching `git log`).
9. **Never stage the whole tree.** `git add -A`, `git add frontend/src` and `git commit -a` are all forbidden. Always stage the explicit file list from the task's Files block.

> ### Starting state: an uncommitted base
>
> When this plan was written the aurora-glass design in the working tree was
> **uncommitted** — `HEAD` carried a 14-line `index.css` and three of the files it
> depends on did not exist at all. The user chose to leave it that way.
>
> Two consequences, both accepted:
>
> - Files this plan **rewrites wholesale** (`index.css`, `index.html`,
>   `Layout.tsx`, `ThemeToggle.tsx`) necessarily carry the aurora content into
>   their commit, because `HEAD` holds no other version of them.
> - Files this plan **edits in place** commit cleanly against the uncommitted
>   state, so those commits will not replay onto `HEAD` on their own.
>
> Rule 9 exists because of this: a blanket `git add -A` in Task 4 would sweep all
> 1331 lines of that uncommitted design into a commit titled "a PICO-8 pixel
> styling system", burying work that is not this plan's.

### Deliberate refinement of the spec

The spec names primitives `.px-panel`, `.px-btn`, `.px-input`, `.px-badge`, `.px-well`, `.px-frame`, `.px-titlebar`, `.px-tab`, `.px-rule`, `.px-scroll`, `.px-dither`, `.px-stripes`. This plan keeps those exact names. The spec's table also implies a `.px-card` with no shadow and `.px-btn--danger`; both exist here.

Two spec details are resolved differently, deliberately:

- **`.px-select`** is a modifier on `.px-input` (`.px-input.px-select`), not a separate base class, because the existing `.select` shares every property with `.input` and only adds a chevron background.
- **`ScoreRing` is a React component, not a CSS class.** A ring made of 20 rotated rectangles cannot be expressed in CSS; `.px-ring` does not exist.

---

> ### Testing notes, learned while executing
>
> - **`Layout` cannot render bare.** It calls `useQueryClient()` and
>   `VerifyEmailBanner` runs a `["me"]` query, so any test rendering it needs a
>   real `QueryClientProvider` with retries off, or every assertion throws
>   `No QueryClient set`.
> - **`Layout` renders deliberate duplicates.** There are two
>   `<nav aria-label="Primary">` (desktop sidebar + mobile tab strip) and two
>   `user.login` renderings (title bar + sidebar "SIGNED IN" well). A
>   screen-wide `getByRole`/`getByText` will throw. Scope with `within(...)` for
>   the sidebar, or use `getAllByText` with an explicit `toHaveLength` — which
>   pins both placements instead of loosening to "at least one".
> - **Test files containing JSX must be `.tsx`.** esbuild's `.ts` loader rejects
>   it, and the failure is a parse error rather than a clean module-resolution
>   error, which makes the "verify it fails first" step misleading.
> - **`--accent-glow` is now undefined.** Two references survive until Task 10
>   rewrites the files that own them (`pages/LoginPage.tsx`,
>   `pages/DashboardPage.tsx`). They are silent no-ops until then.

## File Structure

**Created**

| path | responsibility |
| --- | --- |
| `frontend/src/lib/palette.ts` | Single source of truth for severity, pillar, and status colour + label, and the one score-threshold table. Replaces `PILLAR_LABELS` (×4), `SEVERITY_STYLES` (×3), `scoreTone`/`tone` (×2). |
| `frontend/src/components/PixelIcon.tsx` | Grid-string → `crispEdges` SVG. Owns the icon sprite table. |
| `frontend/src/components/Meter.tsx` | `<Meter>` (20 discrete cells) and `<ScoreRing>` (20 radial cells). |
| `frontend/src/components/EmptyState.tsx` | Exports **both** `EmptyState` and `Loading`. `Loading` is nine lines and shares the frame, so a separate module would exist only to be imported once per page. |
| `frontend/src/test/palette.test.ts` | Every severity/pillar/status resolved for both themes; thresholds monotonic. |
| `frontend/src/test/Meter.test.tsx` | 20 cells, dither at zero, `progressbar` ARIA. |
| `frontend/src/test/PixelIcon.test.tsx` | Every grid rectangular and binary. **Must be `.tsx`** — the test body contains JSX, which esbuild's `.ts` loader rejects. |
| `frontend/src/test/Layout.test.tsx` | Title bar, sidebar placement, skip link, window dots. |
| `frontend/src/test/ScoreHero.test.tsx` | Six meters, `findings === 0` claims no score, basis warning verbatim. |
| `frontend/src/test/EmptyState.test.tsx` | Empty-state copy, action link, loading rows. |

**Rewritten**

| path | responsibility |
| --- | --- |
| `frontend/index.html` | Three fonts, pixel favicon, `theme-color` per theme. |
| `frontend/src/index.css` | The entire styling system. |
| `frontend/src/components/Layout.tsx` | Window chrome + sidebar. |
| `frontend/src/components/ThemeToggle.tsx` | Two `PixelIcon`s, blocky state. |

**Restyled in place** — `App.tsx`, `components/StatusPill.tsx`, `components/VerifyEmailBanner.tsx`, `components/ScoreHero.tsx`, `components/FindingsTable.tsx`, `components/ApprovalQueue.tsx`, `components/TrustPanel.tsx`, `components/HistoryCompare.tsx`, `components/ExploreTab.tsx`, `components/RemediationPlan.tsx`, `components/AgentChat.tsx`, `pages/DashboardPage.tsx`, `pages/ReposPage.tsx`, `pages/AnalysisDetailPage.tsx`, `pages/LoginPage.tsx`.

**Untouched** — everything under `frontend/src/api/`, `frontend/src/lib/theme.ts`, `frontend/src/lib/clipboard.ts`, `frontend/src/lib/buildFixPrompt.ts`, `frontend/vite.config.ts`, `frontend/nginx.conf`, all 7 existing tests.

---

## Class Migration Table

Task 4 rewrites `index.css` and migrates every call site with a script. This table is the whole contract — no other class renames are permitted.

| old | new |
| --- | --- |
| `panel` | `px-panel` |
| `card` `card-hover` | `px-card` |
| `bezel` `bezel-core` | `px-frame` |
| `glass-pill` | *(deleted — Layout only)* |
| `eyebrow` | `px-eyebrow` |
| `btn` | `px-btn` |
| `btn-primary` | `px-btn--primary` |
| `btn-ghost` | `px-btn--ghost` |
| `btn-quiet` | `px-btn--quiet` |
| `btn-ink` | `px-btn--ink` |
| `btn-danger` | `px-btn--danger` |
| `input` | `px-input` |
| `select` | `px-input px-select` |
| `chip` | `px-badge` |
| `link` | `px-link` |
| `skip-link` | `px-skip` |
| `seg` `seg-item` `seg-item-active` `seg-indicator` | *(deleted — replaced by `px-tabs` / `px-tab` in Tasks 5 and 8)* |
| `hairline` | `line` |
| `hairline-strong` | `line-strong` |
| `solid` | `surface` |
| `anim-rise` | `anim-step-in` |
| `anim-pulse-soft` | `anim-blink` |
| `ease-glide` | `ease-step` |

Every `rounded-*` utility is deleted from every call site. Every `bg-*/SOFT` and `border-*/NN` opacity modifier survives unchanged.

---

### Task 1: Palette module

**Files:**
- Create: `frontend/src/lib/palette.ts`
- Create: `frontend/src/test/palette.test.ts`

**Interfaces:**
- Consumes: nothing.
- Produces:
  ```ts
  export type Theme = "dark" | "light";
  export type Severity = "critical" | "high" | "medium" | "low" | "info";
  export type Pillar = "security" | "code-quality" | "testing" | "architecture" | "documentation" | "dependencies";
  export type RunStatus = "pending" | "running" | "done" | "failed";

  export const PILLARS: readonly Pillar[];                 // canonical display order
  export const PILLAR_LABELS: Record<Pillar, string>;
  export const PILLAR_COLOR_VAR: Record<Pillar, string>;  // BARE custom-property
                                                       // name, e.g. "--pillar-security"
  export const SEVERITIES: readonly Severity[];
  export const SEVERITY_COLOR_VAR: Record<Severity, string>;  // "--sev-critical"
  export const STATUS_COLOR_VAR: Record<RunStatus, string>;   // "--status-done"

  /** "ok" | "info" | "warn" | "danger" — the ONE score threshold table. */
  export function scoreTone(score: number): "ok" | "info" | "warn" | "danger";
  /** Resolves a --var reference to a literal for the given theme. Used by
   *  ScoreRing/AnimatedNumber, which paint into SVG attributes. */
  export function colorFor(name: string, theme: Theme): string;
  ```

> **The `*_COLOR_VAR` constants hold BARE custom-property names, not `var(…)`
> wrappers.** `"--status-done"`, never `"var(--status-done)"`. Every call site
> wraps them itself — `` `var(${STATUS_COLOR_VAR[key]})` `` — because
> `colorFor` also accepts bare names and strips a `var()` prefix defensively.
> Emitting the wrapper from the constant would produce `var(var(--x))` at every
> call site, which is invalid CSS.

- [ ] **Step 1: Write the failing test**

`frontend/src/test/palette.test.ts`:

```ts
import { describe, expect, it } from "vitest";
import {
  PILLARS,
  PILLAR_COLOR_VAR,
  PILLAR_LABELS,
  SEVERITIES,
  SEVERITY_COLOR_VAR,
  STATUS_COLOR_VAR,
  colorFor,
  scoreTone,
} from "../lib/palette";

const PICO8 = new Set([
  "#000000", "#1D2B53", "#7E2553", "#008751", "#AB5236", "#5F574F", "#C2C3C7",
  "#FFF1E8", "#FF004D", "#FFA300", "#FFEC27", "#00E436", "#29ADFF", "#83769C",
  "#FF77A8", "#FFCCAA",
]);

describe("palette", () => {
  it("assigns a colour to every pillar in both themes, from the PICO-8 set", () => {
    for (const pillar of PILLARS) {
      for (const theme of ["dark", "light"] as const) {
        expect(PICO8.has(colorFor(PILLAR_COLOR_VAR[pillar], theme))).toBe(true);
      }
    }
  });

  it("assigns a colour to every severity in both themes, from the PICO-8 set", () => {
    for (const severity of SEVERITIES) {
      for (const theme of ["dark", "light"] as const) {
        expect(PICO8.has(colorFor(SEVERITY_COLOR_VAR[severity], theme))).toBe(true);
      }
    }
  });

  it("assigns a colour to every run status in both themes", () => {
    for (const status of ["pending", "running", "done", "failed"] as const) {
      for (const theme of ["dark", "light"] as const) {
        expect(PICO8.has(colorFor(STATUS_COLOR_VAR[status], theme))).toBe(true);
      }
    }
  });

  it("uses all six pillars exactly once, in a fixed order", () => {
    expect(PILLARS).toEqual([
      "security", "code-quality", "testing", "architecture", "documentation", "dependencies",
    ]);
    expect(new Set(PILLARS).size).toBe(6);
  });

  it("labels every pillar and severity", () => {
    for (const pillar of PILLARS) expect(PILLAR_LABELS[pillar]).toBeTruthy();
    // bare custom-property name, NOT a var() wrapper — see the note above
    for (const severity of SEVERITIES) expect(SEVERITY_COLOR_VAR[severity]).toMatch(/^--/);
  });

  it("thresholds scores monotonically", () => {
    expect(scoreTone(100)).toBe("ok");
    expect(scoreTone(80)).toBe("ok");
    expect(scoreTone(79)).toBe("info");
    expect(scoreTone(60)).toBe("info");
    expect(scoreTone(59)).toBe("warn");
    expect(scoreTone(40)).toBe("warn");
    expect(scoreTone(39)).toBe("danger");
    expect(scoreTone(0)).toBe("danger");
  });

  it("resolves an unknown reference to the canvas rather than throwing", () => {
    expect(colorFor("var(--nope)", "dark")).toBe("#000000");
  });
});
```

- [ ] **Step 2: Run the test to verify it fails**

```bash
cd frontend && npx vitest run src/test/palette.test.ts
```
Expected: FAIL — `Cannot find module '../lib/palette'`.

- [ ] **Step 3: Write the implementation**

`frontend/src/lib/palette.ts`:

```ts
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
```

- [ ] **Step 4: Run the test to verify it passes**

```bash
cd frontend && npx vitest run src/test/palette.test.ts
```
Expected: PASS, 7 tests.

- [ ] **Step 5: Commit**

```bash
cd /home/krtk2/Docs/Projects/AI_Inteligence && git add frontend/src/lib/palette.ts frontend/src/test/palette.test.ts
git commit -m "feat - one palette module for severity, pillar and status colour"
```

---

### Task 2: PixelIcon

**Files:**
- Create: `frontend/src/components/PixelIcon.tsx`
- Create: `frontend/src/test/PixelIcon.test.tsx` — **`.tsx`, not `.ts`**: the test
  body contains JSX and esbuild's `.ts` loader rejects it.

**Interfaces:**
- Consumes: nothing.
- Produces:
  ```ts
  export type PixelIconName = keyof typeof ICONS;
  export interface PixelIconProps {
    name: PixelIconName;
    size?: number;      // default 16
    className?: string; // merged onto the <svg>
    title?: string;     // accessible name; omit for decorative use
  }
  export function PixelIcon(props: PixelIconProps): JSX.Element;
  export const ICONS: Record<string, readonly string[]>; // grid strings, for tests
  ```

- [ ] **Step 1: Write the failing test**

`frontend/src/test/PixelIcon.test.tsx`:

```ts
import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { ICONS, PixelIcon } from "../components/PixelIcon";

describe("PixelIcon", () => {
  it("has only rectangular, binary grids", () => {
    for (const [name, grid] of Object.entries(ICONS)) {
      const width = grid[0].length;
      expect(grid.length, `${name} must have at least one row`).toBeGreaterThan(0);
      for (const row of grid) {
        expect(row.length, `${name} row is not ${width} wide`).toBe(width);
        expect(/^[.#o]+$/.test(row), `${name} row "${row}" is not binary`).toBe(true);
      }
    }
  });

  it("renders one rect per lit cell", () => {
    const { container } = render(<PixelIcon name="chevron-down" />);
    const lit = ICONS["chevron-down"].join("").split("").filter((c) => c === "#").length;
    expect(container.querySelectorAll("rect")).toHaveLength(lit);
  });

  it("paints crisp edges and inherits colour", () => {
    const { container } = render(<PixelIcon name="sun" />);
    const svg = container.querySelector("svg")!;
    expect(svg.getAttribute("shape-rendering")).toBe("crispEdges");
    expect(svg.getAttribute("fill")).toBe("currentColor");
  });

  it("is decorative unless given a title", () => {
    const { container, rerender } = render(<PixelIcon name="sun" />);
    expect(container.querySelector("svg")!.getAttribute("aria-hidden")).toBe("true");
    rerender(<PixelIcon name="sun" title="Light theme" />);
    expect(screen.getByTitle("Light theme")).toBeInTheDocument();
  });
});
```

- [ ] **Step 2: Run the test to verify it fails**

```bash
cd frontend && npx vitest run src/test/PixelIcon.test.tsx
```
Expected: FAIL — `Cannot find module '../components/PixelIcon'`.

- [ ] **Step 3: Write the implementation**

`frontend/src/components/PixelIcon.tsx`:

> **Every grid below is `#`/`.`, never `1`/`0`.** The art in this design reads as
> `1`/`0` in a code block, but `cellsOf` only lights `#` and `o`, so a digit grid
> renders an invisible icon. 139 of the 139 rows are literal; `PixelIcon.test.tsx`
> is the check that keeps it that way — when a row comes out blank, suspect a
> digit before suspecting the renderer.

```tsx
/**
 * Icons as grid strings. `#` is ink, `.` is transparent, `o` is a second ink
 * used only for the robot's eyes; one character is one pixel. Every icon is
 * rendered with `shape-rendering: crispEdges` so it lands on whole device pixels
 * at any size — the one rule that separates a pixel icon from a smooth SVG that
 * happens to be small.
 *
 * This replaces three hand-written smooth SVGs (SunIcon, MoonIcon, GitHubMark),
 * the chevron that was baked into a CSS data-URI on `.select`, and the loose
 * Unicode glyphs (`✓ ✗ ⊘ ▲ ▼ →`) typed inline as text.
 */

export const ICONS = {
  /* Navigation and chrome */
  "chevron-down": [
    "100000001",
    "110000011",
    "111000111",
    "111111111",
    "011111110",
    "001111100",
    "000111000",
    "000010000",
    "000000000",
  ],
  "chevron-right": [
    "000100000",
    "001100000",
    "011100000",
    "111111110",
    "011100000",
    "001100000",
    "000100000",
  ],
  "arrow-left": [
    "000010000",
    "000011000",
    "000111000",
    "001111000",
    "111111111",
    "001111000",
    "000111000",
    "000011000",
    "000010000",
  ],
  "arrow-right": [
    "000010000",
    "000110000",
    "001110000",
    "011110000",
    "111111111",
    "011110000",
    "001110000",
    "000110000",
    "000010000",
  ],

  /* Theme toggle */
  sun: [
    "000010000",
    "100010001",
    "010101010",
    "001010100",
    "111111111",
    "001010100",
    "010101010",
    "100010001",
    "000010000",
  ],
  moon: [
    "001111100",
    "011111110",
    "111110000",
    "111100000",
    "111100000",
    "111110000",
    "011111110",
    "001111100",
  ],

  /* Brand mark — a filled square with a bite out of the top-right corner. */
  logo: [
    "1111110..",
    "111111...",
    "11111....",
    "1111.....",
    "111......",
    "11.......",
    "1........",
  ],

  /* Login hero — a 16×16 robot head. Every row is exactly 16 characters;
     PixelIcon.test.tsx fails the build if one is not. */
  "robot-open": [
    "....########....",
    "...##oo##oo##...",
    "..############..",
    "..##oo#####oo#..",
    "..############..",
    "..##oo#####oo#..",
    "..############..",
    "..############..",
    "..############..",
    "..#..######..#..",
    "..#..######..#..",
    "..############..",
    "..############..",
    "...##########...",
    "................",
    "................",
  ],
  "robot-blink": [
    "....########....",
    "...##oo##oo##...",
    "..############..",
    "..##oo#####oo#..",
    "..############..",
    "..############..",
    "..############..",
    "..############..",
    "..#..######..#..",
    "..#..######..#..",
    "..############..",
    "..############..",
    "..############..",
    "...##########...",
    "................",
    "................",
  ],

  /* Feedback — the old Unicode glyphs, as sprites. */
  check: [
    "00000001",
    "00000011",
    "10000110",
    "11001100",
    "01111000",
    "00110000",
    "00000000",
    "00000000",
  ],
  cross: [
    "10000001",
    "11000011",
    "01100110",
    "00111100",
    "00011000",
    "00111100",
    "01100110",
    "11000011",
    "10000001",
  ],
  ban: [
    "011111110",
    "110000011",
    "101000101",
    "100100001",
    "101000101",
    "100100001",
    "101000101",
    "110000011",
    "011111110",
  ],
  triangle: [
    "000010000",
    "000111000",
    "001111100",
    "111111111",
    "000010000",
    "000010000",
    "000010000",
    "000000000",
  ],
  copy: [
    "11110000",
    "11110011",
    "10010011",
    "10010000",
    "10011111",
    "10011111",
    "10010000",
    "11110000",
  ],

  /* Providers */
  github: [
    "0111100111000111",
    "1000010100000010",
    "1000000010000010",
    "1011000010110010",
    "1010000000000010",
    "1001100000110010",
    "0111100111000111",
  ],
} as const satisfies Record<string, readonly string[]>;

export type PixelIconName = keyof typeof ICONS;

export interface PixelIconProps {
  name: PixelIconName;
  /** Rendered size in CSS pixels. Defaults to 16. */
  size?: number;
  className?: string;
  /** Supplying this makes the icon labelled; omitting it marks it decorative. */
  title?: string;
}

/**
 * `o` is a second "ink" cell, used by the robot sprite for its eyes. It renders in
 * the same colour — the shape reads at 16px, a two-tone eye would not.
 */
function cellsOf(grid: readonly string[]): Array<{ x: number; y: number }> {
  const cells: Array<{ x: number; y: number }> = [];
  grid.forEach((row, y) => {
    row.split("").forEach((char, x) => {
      if (char === "#" || char === "o") cells.push({ x, y });
    });
  });
  return cells;
}

export function PixelIcon({ name, size = 16, className, title }: PixelIconProps) {
  const grid = ICONS[name] as readonly string[];
  const columns = grid[0].length;
  const rows = grid.length;
  const cell = size / Math.max(columns, rows);
  const labels = title
    ? { role: "img" as const, "aria-label": title }
    : { "aria-hidden": true };

  return (
    <svg
      width={columns * cell}
      height={rows * cell}
      viewBox={`0 0 ${columns} ${rows}`}
      fill="currentColor"
      shapeRendering="crispEdges"
      className={className}
      {...labels}
    >
      {title ? <title>{title}</title> : null}
      {cellsOf(grid).map(({ x, y }) => (
        <rect key={`${x}-${y}`} x={x} y={y} width={1} height={1} />
      ))}
    </svg>
  );
}
```

- [ ] **Step 4: Run the test to verify it passes**

```bash
cd frontend && npx vitest run src/test/PixelIcon.test.tsx
```
Expected: PASS, 4 tests.

- [ ] **Step 5: Lint, typecheck, commit**

```bash
cd frontend && npm run lint && npm run typecheck
cd /home/krtk2/Docs/Projects/AI_Inteligence && git add frontend/src/components/PixelIcon.tsx frontend/src/test/PixelIcon.test.tsx
git commit -m "feat - icons as grid strings, rendered with crisp edges"
```

---

### Task 3: Meter and ScoreRing

**Files:**
- Create: `frontend/src/components/Meter.tsx` — note: no React hooks are needed, so no `react` import
- Create: `frontend/src/test/Meter.test.tsx` — **`.tsx`**: the test body contains JSX

**Interfaces:**
- Consumes: `scoreTone` and `colorFor` from `lib/palette` (Task 1).
- Produces:
  ```ts
  export const METER_CELLS = 20;

  export interface MeterProps {
    value: number | null;   // null === "not measured"; renders as dither
    label: string;
    color?: string;         // CSS colour; defaults to var(--accent)
    /** Counts the readout to the value on mount. Off in tests. */
    animate?: boolean;
  }
  export function Meter(props: MeterProps): JSX.Element;

  export interface ScoreRingProps {
    value: number;
    tone?: "ok" | "info" | "warn" | "danger";
    theme: Theme;
    size?: number;
  }
  export function ScoreRing(props: ScoreRingProps): JSX.Element;
  ```

- [ ] **Step 1: Write the failing test**

`frontend/src/test/Meter.test.tsx`:

```tsx
import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { METER_CELLS, Meter, ScoreRing } from "../components/Meter";

describe("Meter", () => {
  it("renders exactly 20 cells", () => {
    render(<Meter value={55} label="Testing" />);
    expect(screen.getByRole("progressbar").querySelectorAll("[data-lit]")).toHaveLength(
      METER_CELLS,
    );
  });

  it("fills 11 of 20 cells at 55", () => {
    render(<Meter value={55} label="Testing" />);
    const lit = screen
      .getByRole("progressbar")
      .querySelectorAll('[data-lit="true"]');
    expect(lit).toHaveLength(11);
  });

  it("dithers and drops the value when the number is null", () => {
    const { container } = render(<Meter value={null} label="Dependencies" />);
    expect(container.querySelector(".px-dither")).not.toBeNull();
    // "not measured" must not read as a score, and must not read as zero either.
    expect(screen.queryByText("0")).toBeNull();
    expect(screen.getByText("—")).toBeInTheDocument();
  });

  it("carries the label and value to assistive tech", () => {
    render(<Meter value={72} label="Security" />);
    const bar = screen.getByRole("progressbar", { name: "Security" });
    expect(bar).toHaveAttribute("aria-valuenow", "72");
    expect(bar).toHaveAttribute("aria-valuemin", "0");
    expect(bar).toHaveAttribute("aria-valuemax", "100");
  });
});

describe("ScoreRing", () => {
  it("lights 20% of the ring for a score of 20", () => {
    const { container } = render(<ScoreRing value={20} tone="ok" theme="dark" />);
    expect(container.querySelectorAll('[data-lit="true"]')).toHaveLength(4);
  });

  it("lights every cell at 100", () => {
    const { container } = render(<ScoreRing value={100} tone="ok" theme="dark" />);
    expect(container.querySelectorAll('[data-lit="true"]')).toHaveLength(METER_CELLS);
  });

  it("paints with a literal hex, since a CSS variable cannot be read back", () => {
    const { container } = render(<ScoreRing value={60} tone="ok" theme="dark" />);
    expect(container.innerHTML).toContain("#00E436");
  });
});
```

- [ ] **Step 2: Run the test to verify it fails**

```bash
cd frontend && npx vitest run src/test/Meter.test.tsx
```
Expected: FAIL — `Cannot find module '../components/Meter'`.

- [ ] **Step 3: Write the implementation**

`frontend/src/components/Meter.tsx`:

```tsx

import { colorFor, type Theme } from "../lib/palette";

/**
 * One 20-cell meter unit, 5% per cell, shared by four displays: the score ring,
 * the six pillar meters, verification coverage, and human acceptance by category.
 * They share it so they read as one instrument instead of four unrelated bars.
 *
 * Cells are discrete rather than a continuous fill because that is the point of
 * the whole aesthetic — and because a cell grid survives being resized and
 * scaled without looking like a gradient that happens to be thin.
 */
export const METER_CELLS = 20;

const TONE_VAR: Record<"ok" | "info" | "warn" | "danger", string> = {
  ok: "var(--ok)",
  info: "var(--info)",
  warn: "var(--warn)",
  danger: "var(--danger)",
};

export interface MeterProps {
  /** `null` means "nobody measured this" — not zero, and not a full bar either. */
  value: number | null;
  label: string;
  color?: string;
  animate?: boolean;
}

export function Meter({ value, label, color = "var(--accent)", animate = true }: MeterProps) {
  const filled = value === null ? 0 : Math.round((Math.min(value, 100) / 100) * METER_CELLS);

  return (
    <div
      className="flex items-center gap-2"
      role="progressbar"
      aria-label={label}
      aria-valuenow={value ?? undefined}
      aria-valuemin={0}
      aria-valuemax={100}
    >
      <span
        className={`flex gap-[2px] border-2 border-line bg-canvas p-[2px] ${
          value === null ? "px-dither border-line-strong" : ""
        }`}
      >
        {Array.from({ length: METER_CELLS }, (_, index) => (
          <span
            key={index}
            data-lit={index < filled}
            className="block h-[8px] w-[8px] transition-colors duration-300"
            style={
              value === null
                ? undefined
                : {
                    background: index < filled ? color : "var(--line-strong)",
                    opacity: index < filled ? 1 : 0.35,
                    animation: animate && index < filled ? "cell-on 480ms steps(4, end) both" : undefined,
                    animationDelay: animate ? `${index * 40}ms` : undefined,
                  }
            }
          />
        ))}
      </span>
      <span className="w-9 shrink-0 text-right font-ui text-[13px] tabular-nums">
        {value === null ? "—" : Math.round(value)}
      </span>
    </div>
  );
}

export interface ScoreRingProps {
  value: number;
  tone?: "ok" | "info" | "warn" | "danger";
  theme: Theme;
  size?: number;
}

/**
 * The smooth conic-gradient donut is gone. This is 20 rectangles placed around a
 * circle by rotation, which is what a segmented gauge looks like when it has to
 * render on whole pixels. The segments are rectangles rather than arcs precisely
 * because arcs cannot be crisp.
 */
export function ScoreRing({ value, tone = "ok", theme, size = 132 }: ScoreRingProps) {
  const filled = Math.round((Math.min(Math.max(value, 0), 100) / 100) * METER_CELLS);
  const ringColor = colorFor(TONE_VAR[tone], theme);
  const radius = size / 2 - 9;

  return (
    <div className="grid place-items-center" style={{ width: size, height: size }}>
      <svg width={size} height={size} viewBox={`0 0 ${size} ${size}`} aria-hidden="true">
        {Array.from({ length: METER_CELLS }, (_, index) => {
          // An unlit segment cannot use `fill="var(--line-strong)"`: a CSS
          // variable is only valid in the `fill` *property*, never in the
          // presentation attribute. Hence style, not fill.
          const isLit = index < filled;
          const degrees = (index / METER_CELLS) * 360 - 90;
          return (
            <rect
              key={index}
              data-lit={isLit}
              x={size / 2 - 3}
              y={size / 2 - radius - 5}
              width={6}
              height={10}
              transform={`rotate(${degrees} ${size / 2} ${size / 2})`}
              style={{
                fill: isLit ? ringColor : "var(--line-strong)",
                opacity: isLit ? 1 : 0.35,
                animation: isLit ? "cell-on 480ms steps(4, end) both" : undefined,
                animationDelay: isLit ? `${index * 30}ms` : undefined,
              }}
            />
          );
        })}
      </svg>
      <span
        className="absolute font-ui text-[40px] leading-none tabular-nums"
        style={{ color: ringColor }}
      >
        {value}
      </span>
    </div>
  );
}
```

- [ ] **Step 4: Run the test to verify it passes**

```bash
cd frontend && npx vitest run src/test/Meter.test.tsx
```
Expected: PASS, 7 tests. If the ring colour test fails, the cause is a `fill`
attribute instead of a `fill` style — fix the binding, not the expectation.

- [ ] **Step 5: Lint, typecheck, commit**

```bash
cd frontend && npm run lint && npm run typecheck
cd /home/krtk2/Docs/Projects/AI_Inteligence && git add frontend/src/components/Meter.tsx frontend/src/test/Meter.test.tsx
git commit -m "feat - a 20-cell meter and a blocky score ring"
```

---

### Task 4: Rewrite the styling system

The largest task. Two halves that must land together: the new `index.css`, and a
scripted migration of every call site onto the new class and token names. Landing
the CSS alone breaks the app; landing the migration alone breaks it too.

**Files:**
- Modify: `frontend/src/index.css` (full rewrite)
- Modify: `frontend/index.html` (fonts, favicon, theme-color)
- Modify: every `.tsx` under `frontend/src/` that references a renamed class

**Interfaces:**
- Consumes: `PixelIconName` from Task 2 (for `index.html`'s favicon, which is a
  static data-URI rather than the component), and the token names below.
- Produces: the CSS custom properties and the `.px-*` classes the rest of the
  plan targets. After this task, no `.tsx` references a removed class.

- [ ] **Step 1: Verify the migration is needed and capture the baseline**

```bash
cd frontend && npm run lint && npm run typecheck && npm test && npm run build
```
Expected: all four pass, unchanged from `main`. If any fail before you start, stop
and report — do not build a redesign on a red baseline.

```bash
cd frontend/src && grep -rlo "hairline" --include=*.tsx . | sort
```
Expected: 9 files. Note them; the migration in Step 4 must leave zero.

- [ ] **Step 2: Write `index.css`**

Replace the entire file with:

```css
@import "tailwindcss";

/* Class-based theming: `dark:` utilities follow the `.dark` class on <html>,
   which lib/theme.ts toggles (dark default, persisted to localStorage). */
@custom-variant dark (&:where(.dark, .dark *));

@theme {
  /* Silkscreen carries every UI atom and every number. Pixelify Sans carries
     prose. JetBrains Mono carries paths, SHAs and tool names.
     `font-sans` stays the name so `body`'s @apply and any existing `font-sans`
     utility keep resolving — only the family behind it changed. */
  --font-sans: "Pixelify Sans", ui-sans-serif, system-ui, -apple-system, sans-serif;
  --font-ui: "Silkscreen", "Pixelify Sans", ui-sans-serif, monospace;
  --font-mono: "JetBrains Mono", ui-monospace, SFMono-Regular, Menlo, monospace;

  /* Steps, not glides. Nothing in this system eases smoothly. */
  --ease-step: steps(3, end);
}

@theme inline {
  --color-canvas: var(--canvas);
  --color-surface: var(--surface);
  --color-surface-2: var(--surface-2);
  --color-line: var(--line);
  --color-line-strong: var(--line-strong);
  --color-ink: var(--ink);
  --color-muted: var(--muted);
  --color-faint: var(--faint);
  --color-accent: var(--accent);
  --color-accent-strong: var(--accent-strong);
  --color-accent-ink: var(--accent-ink);
  --color-accent-soft: var(--accent-soft);
  --color-ok: var(--ok);
  --color-ok-soft: var(--ok-soft);
  --color-warn: var(--warn);
  --color-warn-soft: var(--warn-soft);
  --color-danger: var(--danger);
  --color-danger-soft: var(--danger-soft);
  --color-info: var(--info);
  --color-info-soft: var(--info-soft);
  --color-hypo: var(--hypo);
  --color-hypo-soft: var(--hypo-soft);
}

/* ---- Light: Game Boy paper. Same 16 colours, re-picked for contrast on cream. */
:root {
  color-scheme: light;

  --canvas: #c2c3c7;
  --surface: #fff1e8;
  --surface-2: #c2c3c7;

  --line: #5f574f;
  --line-strong: #1d2b53;

  --ink: #000000;
  --muted: #5f574f;
  --faint: #83769c;

  --accent: #1d2b53;
  --accent-strong: #7e2553;
  --accent-ink: #fff1e8;

  --ok: #008751;
  --warn: #ab5236;
  --danger: #ff004d;
  --info: #1d2b53;
  --hypo: #7e2553;

  --shadow: #5f574f;
  --bevel-hi: rgba(255, 255, 255, 0.55);
  --bevel-lo: rgba(0, 0, 0, 0.3);

  --pillar-security: #ff004d;
  --pillar-code-quality: #ab5236;
  --pillar-testing: #1d2b53;
  --pillar-architecture: #7e2553;
  --pillar-documentation: #008751;
  --pillar-dependencies: #5f574f;

  --sev-critical: #ff004d;
  --sev-high: #ab5236;
  --sev-medium: #7e2553;
  --sev-low: #1d2b53;
  --sev-info: #5f574f;

  --status-pending: #5f574f;
  --status-running: #ab5236;
  --status-done: #008751;
  --status-failed: #ff004d;

  /* Dither needs two *different* entries, and in light mode --surface-2 and
     --canvas are the same grey — so the pair is chosen per theme rather than
     derived. Cream on grey reads on both a grey canvas and a cream panel. */
  --dither-a: #fff1e8;
  --dither-b: #c2c3c7;
}

/* ---- Dark: pure black canvas, dark-blue panels. The default. */
.dark {
  color-scheme: dark;

  --canvas: #000000;
  --surface: #1d2b53;
  --surface-2: #000000;

  --line: #5f574f;
  --line-strong: #c2c3c7;

  --ink: #fff1e8;
  --muted: #c2c3c7;
  --faint: #83769c;

  --accent: #29adff;
  --accent-strong: #ffec27;
  --accent-ink: #000000;

  --ok: #00e436;
  --warn: #ffa300;
  --danger: #ff004d;
  --info: #ffec27;
  --hypo: #ff77a8;

  --shadow: #000000;
  --bevel-hi: rgba(255, 241, 232, 0.1);
  --bevel-lo: rgba(0, 0, 0, 0.55);

  --pillar-security: #ff004d;
  --pillar-code-quality: #ffa300;
  --pillar-testing: #29adff;
  --pillar-architecture: #83769c;
  --pillar-documentation: #ff77a8;
  --pillar-dependencies: #00e436;

  --sev-critical: #ff004d;
  --sev-high: #ffa300;
  --sev-medium: #ffec27;
  --sev-low: #29adff;
  --sev-info: #c2c3c7;

  --status-pending: #83769c;
  --status-running: #ffec27;
  --status-done: #00e436;
  --status-failed: #ff004d;

  --dither-a: #1d2b53;
  --dither-b: #000000;
}

/* Every `-soft` tint is a mix of exactly two palette entries — which is what a
   PICO-8 dither between those two colours looks like averaged. This is the only
   reason a tint is allowed to exist at all. */
:root,
.dark {
  --accent-soft: color-mix(in srgb, var(--accent) 22%, var(--surface));
  --ok-soft: color-mix(in srgb, var(--ok) 22%, var(--surface));
  --warn-soft: color-mix(in srgb, var(--warn) 22%, var(--surface));
  --danger-soft: color-mix(in srgb, var(--danger) 22%, var(--surface));
  --info-soft: color-mix(in srgb, var(--info) 22%, var(--surface));
  --hypo-soft: color-mix(in srgb, var(--hypo) 22%, var(--surface));

  /* Pixel metrics. Every border is 2px; shadows are hard offsets with no blur. */
  --px-border: 2px;
  --px-offset: 4px;
  --px-cell: 8px;
}

@layer base {
  html {
    background: var(--canvas);
    -webkit-text-size-adjust: 100%;
  }

  body {
    @apply font-sans;
    margin: 0;
    min-height: 100dvh;
    background: transparent;
    color: var(--ink);
    -webkit-font-smoothing: none;
    -moz-osx-font-smoothing: grayscale;
  }

  /* The hard guarantee behind constraint 2. A stray `rounded-full` left over from
     the old design renders square rather than silently reintroducing a circle. */
  *,
  *::before,
  *::after {
    border-radius: 0;
  }

  /* 8px dot grid — the meter cell unit reused as texture. */
  body::before {
    content: "";
    position: fixed;
    inset: 0;
    z-index: -2;
    pointer-events: none;
    background-image: radial-gradient(
      circle,
      color-mix(in srgb, var(--line) 22%, transparent) 1px,
      transparent 1px
    );
    background-size: 8px 8px;
  }

  /* 2px scanlines, always on. Black at 4% is below the point where it measurably
     costs contrast, and above the point where the screen stops reading as a
     screen. */
  body::after {
    content: "";
    position: fixed;
    inset: 0;
    z-index: -1;
    pointer-events: none;
    background: repeating-linear-gradient(
      to bottom,
      transparent 0 2px,
      rgba(0, 0, 0, 0.04) 2px 4px
    );
  }

  ::selection {
    background: var(--accent);
    color: var(--accent-ink);
  }

  :focus-visible {
    outline: 2px solid var(--accent);
    outline-offset: 0;
  }

  /* On an accent-filled control the accent ring would vanish into it, so the ring
     flips to ink. Focus is never removed — only moved. */
  .px-btn--primary:focus-visible,
  .px-btn--danger:focus-visible,
  .px-tab[aria-selected="true"]:focus-visible {
    outline-color: var(--ink);
  }

  input,
  select,
  textarea,
  button {
    font: inherit;
    color: inherit;
  }
  select option {
    background: var(--surface);
    color: var(--ink);
  }
  input[type="checkbox"] {
    accent-color: var(--accent);
  }
}

@layer components {
  /* ---- Surfaces ---------------------------------------------------------- */

  .px-frame {
    background: var(--surface);
    border: 2px solid var(--line);
    box-shadow: 4px 4px 0 0 var(--shadow);
  }

  .px-panel {
    background: var(--surface);
    border: 2px solid var(--line);
    box-shadow: 4px 4px 0 0 var(--shadow);
  }

  /* A card is a panel whose shadow is suppressed, because a shadow per row in a
     list reads as noise once there are ten of them. */
  .px-card {
    background: var(--surface);
    border: 2px solid var(--line);
  }
  .px-card-hover {
    background: var(--surface);
    border: 2px solid var(--line);
  }
  .px-card-hover:hover {
    background: var(--surface-2);
    border-color: var(--line-strong);
  }

  /* The inverse of a panel: an inset well, which is how this language says
     "this is a screen, not a surface". */
  .px-well {
    background: var(--surface-2);
    border: 2px solid var(--line);
    box-shadow:
      inset 2px 2px 0 0 var(--bevel-lo),
      inset -2px -2px 0 0 var(--bevel-hi);
  }

  .px-rule {
    border-top: 2px solid var(--line);
  }

  .px-titlebar {
    display: flex;
    align-items: center;
    gap: 12px;
    height: 28px;
    padding: 0 10px;
    background: var(--surface);
    border-bottom: 2px solid var(--line);
    font-family: var(--font-ui);
    font-size: 9px;
    letter-spacing: 0.16em;
    text-transform: uppercase;
  }

  .px-eyebrow {
    font-family: var(--font-ui);
    font-size: 9px;
    font-weight: 400;
    letter-spacing: 0.16em;
    text-transform: uppercase;
    color: var(--faint);
  }

  /* ---- Controls ---------------------------------------------------------- */

  .px-btn {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    gap: 6px;
    padding: 7px 12px;
    background: var(--surface-2);
    border: 2px solid var(--line);
    box-shadow: 3px 3px 0 0 var(--shadow);
    font-family: var(--font-ui);
    font-size: 9px;
    font-weight: 700;
    letter-spacing: 0.06em;
    text-transform: uppercase;
    line-height: 1;
    white-space: nowrap;
    cursor: pointer;
    user-select: none;
    transition: transform 80ms steps(2, end), box-shadow 80ms steps(2, end);
  }
  /* The press is physical: the button moves onto its own shadow. */
  .px-btn:hover:not(:disabled) {
    border-color: var(--line-strong);
  }
  .px-btn:active:not(:disabled) {
    transform: translate(2px, 2px);
    box-shadow: 1px 1px 0 0 var(--shadow);
  }
  .px-btn:disabled {
    cursor: not-allowed;
    color: var(--faint);
    background-image: repeating-conic-gradient(
      var(--dither-a) 0% 25%,
      var(--dither-b) 0% 50%
    );
    background-size: 4px 4px;
    box-shadow: none;
  }
  .px-btn-icon {
    padding: 6px;
  }

  .px-btn--primary {
    background: var(--accent);
    color: var(--accent-ink);
    border-color: var(--accent);
  }
  .px-btn--primary:hover:not(:disabled) {
    background: var(--accent-strong);
    border-color: var(--accent-strong);
  }

  .px-btn--danger {
    background: var(--danger);
    color: var(--accent-ink);
    border-color: var(--danger);
  }

  .px-btn--ink {
    background: var(--ink);
    color: var(--canvas);
    border-color: var(--ink);
  }

  .px-btn--ghost {
    background: transparent;
    color: var(--ink);
  }

  .px-btn--quiet {
    padding: 4px 6px;
    background: transparent;
    border-color: transparent;
    box-shadow: none;
    color: var(--muted);
    font-weight: 400;
  }
  .px-btn--quiet:hover:not(:disabled) {
    color: var(--ink);
    background: var(--surface-2);
  }

  .px-input {
    width: 100%;
    padding: 7px 9px;
    background: var(--surface-2);
    border: 2px solid var(--line);
    color: var(--ink);
    font-family: var(--font-sans);
    font-size: 13px;
    line-height: 1.4;
  }
  .px-input::placeholder {
    color: var(--faint);
  }
  .px-input:focus {
    outline: 2px solid var(--accent);
    outline-offset: -2px;
  }
  .px-select {
    appearance: none;
    padding-right: 28px;
    font-family: var(--font-ui);
    font-size: 9px;
    letter-spacing: 0.06em;
  }
  /* The chevron that used to be a baked CSS data-URI is now a sprite overlay, so
     it can inherit the palette instead of hardcoding #7f8f89. */
  .px-select-wrap {
    position: relative;
  }
  .px-select-wrap > .px-select-chevron {
    position: absolute;
    right: 7px;
    top: 50%;
    translate: 0 -50%;
    pointer-events: none;
    color: var(--muted);
  }

  /* ---- Badges ------------------------------------------------------------ */

  .px-badge {
    display: inline-flex;
    align-items: center;
    gap: 5px;
    padding: 3px 6px;
    border: 2px solid var(--line);
    background: var(--surface-2);
    font-family: var(--font-ui);
    font-size: 9px;
    font-weight: 700;
    letter-spacing: 0.06em;
    text-transform: uppercase;
    line-height: 1;
  }
  /* Inside a list row a second shadow competes with the row's own. */
  .px-badge--flat {
    box-shadow: none;
    padding: 2px 5px;
  }

  /* ---- Tabs -------------------------------------------------------------- */

  .px-tabs {
    display: flex;
    border-bottom: 2px solid var(--line);
  }
  .px-tab {
    position: relative;
    padding: 8px 12px;
    background: transparent;
    border: none;
    font-family: var(--font-ui);
    font-size: 9px;
    font-weight: 700;
    letter-spacing: 0.06em;
    text-transform: uppercase;
    color: var(--muted);
    cursor: pointer;
  }
  .px-tab:hover {
    color: var(--ink);
    background: var(--surface-2);
  }
  .px-tab[aria-selected="true"],
  .px-tab[aria-current="page"],
  .px-tab-active {
    color: var(--ink);
  }
  /* An underline rule, not a sliding pill. The old indicator animated a rounded
     capsule across four equal columns; there is nothing to animate here.
     `aria-current` covers react-router's NavLink; `px-tab-active` covers the
     two segmented controls that carry their own class until Task 10 turns them
     into real tablists. */
  .px-tab[aria-selected="true"]::after,
  .px-tab[aria-current="page"]::after,
  .px-tab-active::after {
    content: "";
    position: absolute;
    left: 0;
    right: 0;
    bottom: -2px;
    height: 2px;
    background: var(--accent);
  }

  /* Sidebar variant: a left rule rather than a bottom one. */
  .px-tab--side {
    display: block;
    width: 100%;
    text-align: left;
    padding: 8px 10px;
  }
  .px-tab--side[aria-selected="true"],
  .px-tab--side[aria-current="page"],
  .px-tab--side.px-tab-active {
    background: var(--surface-2);
  }
  .px-tab--side[aria-selected="true"]::after,
  .px-tab--side[aria-current="page"]::after,
  .px-tab--side.px-tab-active::after {
    left: 0;
    right: auto;
    top: 0;
    bottom: 0;
    width: 2px;
    height: auto;
  }

  /* ---- Texture ----------------------------------------------------------- */

  /* A 2px checkerboard of two palette entries: how PICO-8 shades art, and here
     how a surface says "disabled", "loading", or "nobody measured this". */
  .px-dither {
    background-image: repeating-conic-gradient(
      var(--dither-a) 0% 25%,
      var(--dither-b) 0% 50%
    );
    background-size: 4px 4px;
  }
  /* The 1px variant, for table row striping. */
  .px-stripes {
    background-image: repeating-conic-gradient(
      color-mix(in srgb, var(--line) 30%, transparent) 0% 25%,
      transparent 0% 50%
    );
    background-size: 2px 2px;
  }

  /* ---- Scrollbars -------------------------------------------------------- */

  .px-scroll {
    scrollbar-width: thin;
    scrollbar-color: var(--line-strong) var(--surface-2);
  }
  .px-scroll::-webkit-scrollbar {
    width: 12px;
    height: 12px;
  }
  .px-scroll::-webkit-scrollbar-track {
    background: var(--surface-2);
    border: 2px solid var(--line);
  }
  .px-scroll::-webkit-scrollbar-thumb {
    background: var(--line-strong);
    border: 2px solid var(--surface-2);
  }
  .px-scroll::-webkit-scrollbar-corner {
    background: var(--surface-2);
  }

  .px-skip {
    position: absolute;
    left: 8px;
    top: -64px;
    z-index: 60;
    padding: 6px 10px;
    background: var(--surface);
    border: 2px solid var(--accent);
    font-family: var(--font-ui);
    font-size: 9px;
    letter-spacing: 0.06em;
    text-transform: uppercase;
  }
  .px-skip:focus {
    top: 8px;
  }

  .px-link {
    color: var(--accent);
    text-decoration: underline;
    text-underline-offset: 2px;
  }
  .px-link:hover {
    color: var(--accent-strong);
  }
}

@layer utilities {
  /* No blur, no scale, no 18px rise. A 4px hop in three steps. */
  .anim-step-in {
    animation: step-in 240ms steps(3, end) both;
  }
  .anim-blink {
    animation: blink 1100ms steps(2, end) infinite;
  }
  .anim-slide-up {
    animation: slide-up 900ms steps(6, end) infinite;
  }
}

@keyframes step-in {
  from {
    opacity: 0;
    transform: translateY(-4px);
  }
  to {
    opacity: 1;
    transform: none;
  }
}

@keyframes blink {
  0%,
  49% {
    opacity: 1;
  }
  50%,
  100% {
    opacity: 0.35;
  }
}

@keyframes slide-up {
  from {
    transform: translateX(0);
  }
  to {
    transform: translateX(20px);
  }
}

@keyframes cell-on {
  from {
    opacity: 0;
  }
  to {
    opacity: 1;
  }
}

@media (prefers-reduced-motion: reduce) {
  *,
  *::before,
  *::after {
    animation-duration: 0.001ms !important;
    animation-iteration-count: 1 !important;
    transition-duration: 0.001ms !important;
  }
}
```

- [ ] **Step 3: Update `index.html`**

Replace the font link, the favicon, and `theme-color`:

```html
    <meta name="theme-color" content="#1d2b53" />
    <link
      rel="icon"
      href="data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 16 16' shape-rendering='crispEdges'%3E%3Crect width='16' height='16' fill='%23000000'/%3E%3Cpath d='M1 1h11v3H5v3H2V4h-1z' fill='%2329adff'/%3E%3Crect x='2' y='11' width='5' height='4' fill='%23ffec27'/%3E%3C/svg%3E"
    />
    <title>RETRACT</title>
    <link rel="preconnect" href="https://fonts.googleapis.com" />
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin />
    <link
      href="https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;500&family=Pixelify+Sans:wght@400;500;600;700&family=Silkscreen:wght@400;700&display=swap"
      rel="stylesheet"
    />
```

Then make `theme-color` follow the theme, since the dark canvas is now pure black
and the light one is `#c2c3c7` — a single static value would be wrong half the
time. Add this to the existing inline pre-paint script, after the `colorScheme`
line:

```js
        document
          .querySelector('meta[name="theme-color"]')
          .setAttribute("content", dark ? "#1d2b53" : "#c2c3c7");
```

- [ ] **Step 4: Write and run the class migration script**

A blind `sed` would corrupt prose: `input`, `select` and `link` are also English
words that appear in user-visible strings. The script therefore tokenizes only
inside `className` string and template literals.

Write `/tmp/retoken.mjs`:

```js
import { readFileSync, writeFileSync } from "node:fs";
import { execSync } from "node:child_process";

const MAP = {
  "card-hover": "px-card-hover",
  "bezel-core": "px-frame",
  bezel: "px-frame",
  "glass-pill": "px-panel",
  "hairline-strong": "line-strong",
  hairline: "line",
  "seg-item-active": "px-tab-active",
  "seg-item": "px-tab",
  seg: "px-tabs",
  "skip-link": "px-skip",
  eyebrow: "px-eyebrow",
  "btn-primary": "px-btn--primary",
  "btn-danger": "px-btn--danger",
  "btn-ghost": "px-btn--ghost",
  "btn-quiet": "px-btn--quiet",
  "btn-ink": "px-btn--ink",
  btn: "px-btn",
  input: "px-input",
  "solid": "surface",
  select: "px-input px-select",
  chip: "px-badge",
  link: "px-link",
  panel: "px-panel",
  card: "px-card",
  "anim-rise": "anim-step-in",
  "anim-pulse-soft": "anim-blink",
  "ease-glide": "ease-step",
};

const files = execSync("find src -name '*.tsx'", { encoding: "utf8" })
  .trim()
  .split("\n");

const CLASSNAME = /(className\s*=\s*)(["'`])([^"'`]*)\2/g;
const ROUNDED = /^rounded-(full|2xl|xl|lg|md|sm)$/;
let touched = 0;

for (const file of files) {
  const before = readFileSync(file, "utf8");
  const after = before.replace(CLASSNAME, (match, head, quote, body) => {
    const replaced = body
      .split(/\s+/)
      .filter(Boolean)
      .filter((token) => !ROUNDED.test(token))
      .map((token) => {
        const colonless = token.includes(":") ? token.split(":").pop() : token;
        if (MAP[colonless]) {
          const prefix = token.includes(":") ? `${token.split(":")[0]}:` : "";
          return `${prefix}${MAP[colonless]}`;
        }
        return token;
      })
      .join(" ");
    return `${head}${quote}${replaced}${quote}`;
  });
  if (after !== before) {
    writeFileSync(file, after);
    touched += 1;
  }
}

console.log(`rewrote ${touched} files`);
```

Run it:

```bash
cd frontend && node /tmp/retoken.mjs
```
Expected: `rewrote N files` with N > 10.

> The tokenising pass is what makes this safe. `input`, `select` and `link` are
> also ordinary English words that appear in user-visible strings and in
> `aria-label`s, so a blind `sed s/input/px-input/g` would corrupt both the
> markup and the copy. Only whole whitespace-delimited tokens *inside a
> `className` value* are touched, and a `variant:` prefix is preserved so
> `md:panel` becomes `md:px-panel` rather than losing its breakpoint.
>
> `bezel`/`bezel-core` → `px-frame` and `glass-pill` → `px-panel` are deliberate
> intermediate states that Task 5 replaces with the real shell.
> `seg*` → `px-tabs`/`px-tab`/`px-tab-active` keeps both segmented controls
> working from this commit onward; Task 10 upgrades them to real ARIA tablists.

- [ ] **Step 5: Verify the migration is complete**

```bash
cd frontend/src && for token in hairline "solid" "glass-pill" "anim-rise" "anim-pulse-soft" "ease-glide" "rounded-" "btn-" "chip" "eyebrow" "seg-"; do
  printf '%-18s ' "$token"
  if grep -rq -- "$token" --include=*.tsx .; then echo "STILL PRESENT"; else echo "clean"; fi
done
cd frontend/src && grep -rn "rounded-" --include=*.tsx . || echo "OK: no rounded-* remain"
```

Expected: every line `clean`. The `seg-` line will still report `STILL PRESENT`
— `seg-indicator` is a React *key/handler* name in `AnalysisDetailPage`, not a
class, and Task 10 deletes it. Confirm by eye that no `.seg-indicator` class
reference remains:

```bash
cd frontend/src && grep -rn '"seg-indicator"\|seg-indicator' --include=*.tsx . || echo "OK"
```

- [ ] **Step 6: Run the full check suite**

```bash
cd frontend && npm run lint && npm run typecheck && npm test && npm run build
```
Expected: all pass. The 7 existing tests assert on roles, text and placeholders
only, never on a class name — verified by grep in the spec — so a CSS rename
cannot break them. If one does fail, the cause is a string you renamed by
accident, not the CSS.

- [ ] **Step 7: Commit**

```bash
cd /home/krtk2/Docs/Projects/AI_Inteligence
git add frontend/src/index.css frontend/index.html
# plus every .tsx the retoken script rewrote — list them with:
#   git status --porcelain frontend/src | grep '^ M'
git commit -m "feat - a PICO-8 pixel styling system, and migrate every call site onto it"
```

Do **not** run `git add -A`. See Global Constraint 9.

---

### Task 5: Window-chrome shell

**Files:**
- Modify: `frontend/src/components/Layout.tsx` (rewrite)
- Modify: `frontend/src/components/ThemeToggle.tsx` (rewrite)
- Modify: `frontend/src/App.tsx` (Splash)

**Interfaces:**
- Consumes: `PixelIcon` (Task 2), `.px-titlebar` / `.px-frame` / `.px-tab` (Task 4).
- Produces: `Layout({ user, children })` with the same signature as today, so
  `App.tsx` and every page need no change.

- [ ] **Step 1: Write the failing test**

`frontend/src/test/Layout.test.tsx`:

```tsx
import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it } from "vitest";
import { Layout } from "../components/Layout";
import type { User } from "../api/types";

const user: User = {
  id: 1,
  login: "krztk2",
  github_id: null,
  email: "k@example.com",
  email_verified: true,
};

function renderLayout(path = "/") {
  return render(
    <MemoryRouter initialEntries={[path]}>
      <Layout user={user}>
        <p>content</p>
      </Layout>
    </MemoryRouter>,
  );
}

describe("Layout", () => {
  it("renders a window title bar carrying the wordmark", () => {
    const { container } = renderLayout();
    expect(container.querySelector(".px-titlebar")).not.toBeNull();
    expect(screen.getByText("RETRACT")).toBeInTheDocument();
  });

  it("puts navigation in the sidebar, not the title bar", () => {
    const { container } = renderLayout("/repos");
    const sidebar = container.querySelector("nav[aria-label='Primary']")!;
    expect(sidebar).not.toBeNull();
    const link = screen.getByRole("link", { name: /repositories/i });
    expect(sidebar.contains(link)).toBe(true);
    expect(link).toHaveAttribute("aria-current", "page");
  });

  it("keeps a skip link, and it is the first focusable thing", () => {
    renderLayout();
    expect(screen.getByRole("link", { name: /skip to content/i })).toHaveAttribute("href", "#content");
  });

  it("shows the user and a log out control", () => {
    renderLayout();
    expect(screen.getByText("krztk2")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /log out/i })).toBeInTheDocument();
  });

  it("marks the window dots decorative", () => {
    const { container } = renderLayout();
    const dots = container.querySelectorAll("[data-window-dot]");
    expect(dots).toHaveLength(3);
    for (const dot of dots) expect(dot.getAttribute("aria-hidden")).toBe("true");
  });
});
```

- [ ] **Step 2: Run the test to verify it fails**

```bash
cd frontend && npx vitest run src/test/Layout.test.tsx
```
Expected: FAIL — no `.px-titlebar`, and the nav is in the header.

- [ ] **Step 3: Rewrite `Layout.tsx`**

```tsx
import { useQueryClient } from "@tanstack/react-query";
import type { ReactNode } from "react";
import { Link, NavLink } from "react-router-dom";
import { api } from "../api/client";
import type { User } from "../api/types";
import { PixelIcon } from "./PixelIcon";
import { ThemeToggle } from "./ThemeToggle";
import { VerifyEmailBanner } from "./VerifyEmailBanner";

/**
 * The app as a window: a 28px title bar, a sidebar, and content that scrolls on
 * the document.
 *
 * The scroll decision is deliberate. A title bar that sticks and a sidebar that
 * sticks are easy; adding a *third* nested scroll region behind them is not, and
 * this app already has two (the findings table scrolls horizontally, the agent
 * transcript scrolls vertically). So the content column keeps normal page scroll
 * and only the sidebar scrolls independently.
 */
export function Layout({ user, children }: { user: User; children: ReactNode }) {
  const queryClient = useQueryClient();

  async function handleLogout() {
    await api.logout();
    await queryClient.invalidateQueries({ queryKey: ["me"] });
    window.location.reload();
  }

  return (
    <div className="min-h-[100dvh] bg-canvas">
      <a href="#content" className="px-skip">
        Skip to content
      </a>

      <header className="px-titlebar sticky top-0 z-40 justify-between">
        <span className="flex items-center gap-2">
          <PixelIcon name="logo" size={12} className="text-accent" />
          <span className="font-ui text-[13px] font-bold tracking-[0.18em] text-ink">
            RETRACT
          </span>
        </span>

        <span className="ml-auto flex items-center gap-3">
          {/* Decorative window controls. They imply minimise/maximise/close, so
              they are aria-hidden and carry no behaviour — every function they
              might suggest is available as a labelled control beside them. */}
          <span aria-hidden="true" className="flex gap-1">
            <span data-window-dot className="block h-[8px] w-[8px] bg-danger" />
            <span data-window-dot className="block h-[8px] w-[8px] bg-warn" />
            <span data-window-dot className="block h-[8px] w-[8px] bg-ok" />
          </span>
          <ThemeToggle />
          <span className="max-w-[10rem] truncate font-ui text-[9px] text-muted">
            {user.login}
          </span>
          <button onClick={handleLogout} className="px-btn px-btn--quiet">
            Log out
          </button>
        </span>
      </header>

      <div className="mx-auto flex max-w-[1280px] gap-0 px-0 sm:px-4">
        <nav
          aria-label="Primary"
          className="sticky top-[28px] hidden h-[calc(100dvh-28px)] w-[200px] shrink-0 flex-col gap-1 border-r-2 border-line bg-surface p-2 lg:flex"
        >
          <NavLink to="/" end className="px-tab px-tab--side">
            Dashboard
          </NavLink>
          <NavLink to="/repos" className="px-tab px-tab--side">
            Repositories
          </NavLink>

          <span className="mt-auto px-well p-2">
            <span className="block font-ui text-[9px] tracking-[0.16em] text-faint">
              SIGNED IN
            </span>
            <span className="block truncate font-ui text-[11px] text-ink">{user.login}</span>
          </span>
        </nav>

        {/* Below lg the sidebar becomes a tab strip directly under the title bar.
            No hamburger, no drawer — a drawer hides the window metaphor this
            whole design is built on. */}
        <nav
          aria-label="Primary"
          className="px-tabs sticky top-[28px] z-30 w-full overflow-x-auto lg:hidden"
        >
          <NavLink to="/" end className="px-tab">
            Dashboard
          </NavLink>
          <NavLink to="/repos" className="px-tab">
            Repositories
          </NavLink>
        </nav>

        <main id="content" className="min-w-0 flex-1 px-4 pb-24 pt-6 sm:px-6">
          <VerifyEmailBanner />
          {children}
        </main>
      </div>

      <p className="mx-auto max-w-[1280px] px-4 pb-6 text-center font-mono text-[10px] text-faint sm:px-6">
        <Link to="/" className="px-link">
          Retract
        </Link>{" "}
        — repository health, computed not vibes
      </p>
    </div>
  );
}
```

`NavLink` sets `aria-current="page"` on the active link automatically, which is
what the test asserts and what the old `navClass` helper was doing by hand.

- [ ] **Step 4: Rewrite `ThemeToggle.tsx`**

```tsx
import { PixelIcon } from "./PixelIcon";
import { useTheme } from "../lib/theme";

export function ThemeToggle({ className = "" }: { className?: string }) {
  const { theme, toggle } = useTheme();
  const next = theme === "dark" ? "light" : "dark";

  return (
    <button
      onClick={toggle}
      aria-label={`Switch to ${next} theme`}
      title={`Switch to ${next} theme`}
      className={`px-btn px-btn-icon ${className}`}
    >
      {/* keyed on theme so the swap steps rather than crossfades */}
      <span key={theme} className="anim-step-in block">
        <PixelIcon name={theme === "dark" ? "sun" : "moon"} size={12} />
      </span>
    </button>
  );
}
```

`.px-btn-icon` is already defined in Task 4's CSS; do not add it again.

- [ ] **Step 5: Restyle the `Splash` in `App.tsx`**

Replace the pulsing orb with a dithered well and a blinking mark:

```tsx
function Splash() {
  return (
    <div className="grid min-h-[100dvh] place-items-center bg-canvas">
      <div className="px-well flex flex-col items-center gap-3 p-8">
        <span className="anim-blink block text-accent">
          <PixelIcon name="logo" size={24} />
        </span>
        <p className="px-eyebrow">Loading workspace</p>
      </div>
    </div>
  );
}
```

Add the `PixelIcon` import to `App.tsx`.

- [ ] **Step 6: Run the test, then the full suite**

```bash
cd frontend && npx vitest run src/test/Layout.test.tsx
```
Expected: PASS, 5 tests.

```bash
cd frontend && npm run lint && npm run typecheck && npm test && npm run build
```

- [ ] **Step 7: Commit**

```bash
cd /home/krtk2/Docs/Projects/AI_Inteligence && git add frontend/src/components/Layout.tsx frontend/src/components/ThemeToggle.tsx frontend/src/App.tsx frontend/src/index.css frontend/src/test/Layout.test.tsx
git commit -m "feat - the app as a window: title bar, sidebar, no drawer"
```

---

### Task 6: Shared components — StatusPill, EmptyState, Loading, VerifyEmailBanner

**Files:**
- Create: `frontend/src/components/EmptyState.tsx` (exports `EmptyState` and `Loading`)
- Modify: `frontend/src/components/StatusPill.tsx` (rewrite)
- Modify: `frontend/src/components/VerifyEmailBanner.tsx`
- Test: `frontend/src/test/EmptyState.test.tsx`

**Interfaces:**
- Consumes: `PixelIcon` (Task 2), `STATUS_COLOR_VAR` (Task 1).
- Produces:
  ```ts
  export function EmptyState(props: {
    title: string;
    detail?: string;
    action?: { label: string; to: string } | ReactNode;
    icon?: PixelIconName;
  }): JSX.Element;

  export function Loading({ label, rows = 3 }: { label: string; rows?: number }): JSX.Element;
  ```

- [ ] **Step 1: Write the failing test**

`frontend/src/test/EmptyState.test.tsx`:

```tsx
import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it } from "vitest";
import { EmptyState, Loading } from "../components/EmptyState";

describe("EmptyState", () => {
  it("shows a title and an optional detail", () => {
    render(<EmptyState title="No analyses yet" detail="Point it at a repository." />);
    expect(screen.getByText("No analyses yet")).toBeInTheDocument();
    expect(screen.getByText("Point it at a repository.")).toBeInTheDocument();
  });

  it("renders an action link", () => {
    render(
      <MemoryRouter>
        <EmptyState title="Nothing" action={{ label: "Add a repo", to: "/repos" }} />
      </MemoryRouter>,
    );
    expect(screen.getByRole("link", { name: "Add a repo" })).toHaveAttribute("href", "/repos");
  });
});

describe("Loading", () => {
  it("announces the label and draws the requested number of rows", () => {
    const { container } = render(<Loading label="Loading graph…" rows={4} />);
    expect(screen.getByText("Loading graph…")).toBeInTheDocument();
    expect(container.querySelectorAll(".px-dither")).toHaveLength(4);
  });
});
```

- [ ] **Step 2: Run the test to verify it fails**

```bash
cd frontend && npx vitest run src/test/EmptyState.test.tsx
```
Expected: FAIL — `Cannot find module '../components/EmptyState'`.

- [ ] **Step 3: Write `EmptyState.tsx` (which also exports `Loading`)**

The spec lists these as two files. They ship as one: `Loading` is nine lines, it
shares `EmptyState`'s frame, and splitting it would create a module that exists
only to be imported once per page. If a reviewer objects, split it — nothing
depends on the file boundary.

```tsx
import type { ReactNode } from "react";
import { Link } from "react-router-dom";
import { PixelIcon, type PixelIconName } from "./PixelIcon";

export interface EmptyStateProps {
  title: string;
  detail?: string;
  action?: { label: string; to: string } | ReactNode;
  icon?: PixelIconName;
}

/**
 * The app had nine inline empty / error / "nothing here" blocks and eight bare
 * "Loading…" strings, each styled slightly differently and none of them
 * announcing anything to assistive tech. Two components, one frame.
 */
export function EmptyState({ title, detail, action, icon = "logo" }: EmptyStateProps) {
  return (
    <div className="px-well flex flex-col items-center gap-3 p-8 text-center">
      <span className="text-faint">
        <PixelIcon name={icon} size={24} />
      </span>
      <p className="font-ui text-[11px] uppercase tracking-[0.06em] text-ink">{title}</p>
      {detail ? <p className="max-w-[32rem] text-[13px] text-muted">{detail}</p> : null}
      {action ? (
        typeof action === "object" && action !== null && "to" in action ? (
          <Link to={action.to} className="px-btn px-btn--primary">
            {action.label}
          </Link>
        ) : (
          action
        )
      ) : null}
    </div>
  );
}

export function Loading({ label, rows = 3 }: { label: string; rows?: number }) {
  return (
    <div role="status" aria-live="polite" className="flex flex-col gap-2">
      <p className="px-eyebrow">{label}</p>
      {Array.from({ length: rows }, (_, index) => (
        <span
          key={index}
          aria-hidden="true"
          className="px-dither block h-[28px] border-2 border-line"
        />
      ))}
    </div>
  );
}
```

- [ ] **Step 4: Rewrite `StatusPill.tsx`**

The dot becomes a square. The colours come from `palette.ts` rather than a second
copy of the status table.

```tsx
import { STATUS_COLOR_VAR, type RunStatus } from "../lib/palette";

const FALLBACK: RunStatus = "pending";

/**
 * Status is never colour alone: the word is always present, and the glyph
 * blinks only while work is actually in flight.
 */
export function StatusPill({ status }: { status: string }) {
  const key = (status in STATUS_COLOR_VAR ? status : FALLBACK) as RunStatus;
  const color = `var(${STATUS_COLOR_VAR[key]})`;
  const live = key === "running";

  return (
    <span
      className="px-badge"
      style={{ borderColor: color, color }}
    >
      <span
        aria-hidden="true"
        className={`block h-[8px] w-[8px] ${live ? "anim-blink" : ""}`}
        style={{ background: color }}
      />
      {status}
    </span>
  );
}
```

- [ ] **Step 5: Restyle `VerifyEmailBanner.tsx`**

Keep every string — `Resend email`, `Email verified` and `Verification email
sent` are all pinned by `VerifyEmailBanner.test.tsx`. Only the frame changes:

- outer element: `anim-step-in mb-6 flex flex-wrap items-center justify-between gap-3 px-panel px-4 py-3` (drop `rounded-2xl`)
- `Verifying your email` heading: `font-ui text-[9px] uppercase tracking-[0.16em] text-warn`
- body copy: `text-[13px] text-ink`
- `Resend email`: `px-btn px-btn--ghost`
- when verified, swap the frame to `border-ok text-ok` instead of `text-warn`

- [ ] **Step 6: Run the test, then the full suite**

```bash
cd frontend && npx vitest run src/test/EmptyState.test.tsx src/test/VerifyEmailBanner.test.tsx
```
Expected: PASS, 8 tests.

```bash
cd frontend && npm run lint && npm run typecheck && npm test && npm run build
```

- [ ] **Step 7: Commit**

```bash
cd /home/krtk2/Docs/Projects/AI_Inteligence && git add frontend/src/components/EmptyState.tsx frontend/src/components/StatusPill.tsx frontend/src/components/VerifyEmailBanner.tsx frontend/src/test/EmptyState.test.tsx
git commit -m "feat - one empty state, one loading state, one status pill"
```

---

### Task 7: ScoreHero and the three bar call sites

**Files:**
- Modify: `frontend/src/components/ScoreHero.tsx` (rewrite)
- Modify: `frontend/src/components/TrustPanel.tsx`
- Modify: `frontend/src/components/HistoryCompare.tsx`

**Interfaces:**
- Consumes: `Meter`, `ScoreRing` (Task 3), `PILLARS`, `PILLAR_LABELS`,
  `PILLAR_COLOR_VAR`, `scoreTone` (Task 1), `useTheme` (existing).
- Produces: nothing new. All three keep their existing props.

- [ ] **Step 1: Write the failing test**

`frontend/src/test/ScoreHero.test.tsx`:

```tsx
import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { ScoreHero } from "../components/ScoreHero";
import type { Score } from "../api/types";

/** `ScorePillar.score` is always a number. "Not measured" is `findings === 0`,
 *  which is why an absent-looking pillar here is not modelled by a null score. */
const score: Score = {
  version: 3,
  overall: 64,
  loc: 2565,
  kloc: 2.565,
  basis: "density",
  pillars: {
    security: { score: 42, findings: 13, verified: 12, hypotheses: 1 },
    "code-quality": { score: 88, findings: 5, verified: 5, hypotheses: 0 },
    // findings: 0 — nothing triggered this analyzer, so no score is claimed.
    testing: { score: 100, findings: 0, verified: 0, hypotheses: 0 },
    architecture: { score: 61, findings: 3, verified: 2, hypotheses: 1, dismissed: 1 },
    documentation: { score: 90, findings: 2, verified: 2, hypotheses: 0 },
    dependencies: { score: 75, findings: 4, verified: 4, hypotheses: 0 },
  },
};

describe("ScoreHero", () => {
  it("renders one meter per pillar, all six", () => {
    render(<ScoreHero score={score} />);
    for (const label of [
      "Security",
      "Code quality",
      "Testing",
      "Architecture",
      "Documentation",
      "Dependencies",
    ]) {
      expect(screen.getByRole("progressbar", { name: label })).toBeInTheDocument();
    }
  });

  it("claims no score for a pillar with zero findings", () => {
    render(<ScoreHero score={score} />);
    const testing = screen.getByRole("progressbar", { name: "Testing" });
    // aria-valuenow is omitted rather than set to the backend's flattering 100.
    expect(testing).not.toHaveAttribute("aria-valuenow");
    expect(screen.getByText("not measured")).toBeInTheDocument();
  });

  it("keeps the existing count-basis warning verbatim", () => {
    render(<ScoreHero score={{ ...score, basis: "count" }} />);
    expect(
      screen.getByText("No LOC measured — scored on finding count"),
    ).toBeInTheDocument();
  });

  it("returns nothing without a score", () => {
    const { container } = render(<ScoreHero score={null} />);
    expect(container).toBeEmptyDOMElement();
  });
});
```

- [ ] **Step 2: Run the test to verify it fails**

```bash
cd frontend && npx vitest run src/test/ScoreHero.test.tsx
```
Expected: FAIL — no `Meter`, so no `progressbar` roles.

- [ ] **Step 3: Rewrite `ScoreHero.tsx`**

Delete from this file: the local `PILLAR_LABELS`, the local `tone()`, the local
`PILLAR_ORDER`, the `AnimatedNumber` component, and the `conic-gradient` donut
markup. Keep the existing `score: Score | null` signature and the
`if (!score) return null` guard.

```tsx
import { useTheme } from "../lib/theme";
import { Meter, ScoreRing } from "./Meter";
import { PILLARS, PILLAR_COLOR_VAR, PILLAR_LABELS, scoreTone } from "../lib/palette";
import type { Score } from "../api/types";

export function ScoreHero({ score }: { score: Score | null }) {
  const { theme } = useTheme();
  if (!score) return null;

  return (
    <section className="anim-step-in px-panel p-5">
      <div className="flex flex-wrap items-center gap-6">
        <div className="relative shrink-0">
          <ScoreRing value={score.overall} tone={scoreTone(score.overall)} theme={theme} />
        </div>
        <div className="min-w-[16rem] flex-1">
          <p className="px-eyebrow">Repository health</p>
          {score.previous_overall != null ? (
            <p className="font-ui text-[11px] text-muted">
              {score.overall - score.previous_overall >= 0 ? "▲" : "▼"}{" "}
              {Math.abs(score.overall - score.previous_overall)} vs previous
            </p>
          ) : null}
          {score.basis === "count" && (
            <p className="px-badge px-badge--flat mt-2 border-warn text-warn">
              No LOC measured — scored on finding count
            </p>
          )}
        </div>
      </div>

      <div className="mt-5 flex flex-col gap-2 border-t-2 border-line pt-4">
        {PILLARS.map((pillar) => {
          const data = score.pillars[pillar];
          if (!data) return null;
          // A pillar with no findings scores 100, which is indistinguishable from
          // "checked and clean" unless it is labelled. Nothing was found because
          // nothing was measured, and the number must not read as reassurance.
          const unmeasured = data.findings === 0;
          return (
            <div key={pillar} className="flex items-center gap-3">
              <span className="w-[7rem] shrink-0 font-ui text-[9px] uppercase tracking-[0.06em] text-muted">
                {PILLAR_LABELS[pillar]}
              </span>
              <Meter
                value={unmeasured ? null : data.score}
                label={PILLAR_LABELS[pillar]}
                color={`var(${PILLAR_COLOR_VAR[pillar]})`}
              />
              <span className="w-[8.5rem] shrink-0 text-right font-mono text-[10px] text-faint tabular-nums">
                {unmeasured
                  ? "not measured"
                  : `${data.verified}v / ${data.hypotheses}h${
                      data.dismissed != null ? ` / ${data.dismissed}d` : ""
                    }`}
              </span>
            </div>
          );
        })}
      </div>

      {PILLARS.some((pillar) => score.pillars[pillar]?.findings === 0) && (
        <p className="mt-4 border-t-2 border-line pt-3 text-[11px] leading-relaxed text-faint">
          A dimension with no findings is shown as &ldquo;not measured&rdquo;: nothing
          was found because nothing triggered that analyzer, which is not the same
          as clean.
        </p>
      )}
    </section>
  );
}
```

> One visible copy change is unavoidable and accepted: `PILLAR_LABELS` moves from
> `"Code Quality"` to `"Code quality"`, because the labels now render in
> `text-transform: uppercase` Silkscreen and a hardcoded capital in the middle of
> a phrase is wrong for a string that is styled uppercase anyway. No test pins it.
>

- [ ] **Step 4: Replace the two hand-rolled bars in `TrustPanel.tsx`**

`TrustPanel.tsx` builds its coverage and acceptance bars with inline
`style={{ width: ... }}` over a `linear-gradient` track. Replace both with
`<Meter>`, importing it from `./Meter`. Note the units — both API fields are
**0–1 ratios**, not percentages, so multiply:

- `verification_coverage: number | null` → 
  `<Meter value={coverage == null ? null : coverage * 100} label="Verification coverage" color="var(--ok)" />`
- `CalibrationStat.acceptance_rate: number | null` →
  `<Meter value={rate.acceptance_rate == null ? null : rate.acceptance_rate * 100} label={`Human acceptance, ${rate.category}`} color="var(--info)" />`

Keep the surrounding labels, the `—` for a null rate, the per-agent `<table>`,
and every string. Add `px-scroll` to the wrapper so a wide agent table scrolls
with blocky chrome. The four `chip border …` summary badges at the top of the
panel become `px-badge px-badge--flat`.

- [ ] **Step 5: Restyle `HistoryCompare.tsx`**

- `anim-rise mt-5 rounded-2xl border border-hairline bg-surface-2 p-4` →
  `anim-step-in px-well mt-5 p-4`
- the A/B diff `<table>`: `border-t border-hairline` → `border-t-2 border-line`
- delta chips: `▲ +N vs previous` keeps its glyph but moves to
  `px-badge px-badge--flat` with `font-ui`
- delete the local `PILLAR_LABELS` and import from `../lib/palette`
- **the `text-white` left over in this file** — plain Tailwind white is not a
  PICO-8 entry. Replace it with `text-ink` (dark) or `--ink`. Found by the Task 4
  sweep; it is the last non-palette colour outside `AgentChat.tsx`.

- [ ] **Step 6: Run the test, then the full suite**

```bash
cd frontend && npx vitest run src/test/ScoreHero.test.tsx
```
Expected: PASS, 4 tests.

```bash
cd frontend && npm run lint && npm run typecheck && npm test && npm run build
```

- [ ] **Step 7: Commit**

```bash
cd /home/krtk2/Docs/Projects/AI_Inteligence && git add frontend/src/components/ScoreHero.tsx frontend/src/components/TrustPanel.tsx frontend/src/components/HistoryCompare.tsx frontend/src/test/ScoreHero.test.tsx
git commit -m "feat - a blocky score ring and shared 20-cell meters"
```

---

### Task 8: FindingsTable and ApprovalQueue

**Files:**
- Modify: `frontend/src/components/FindingsTable.tsx`
- Modify: `frontend/src/components/ApprovalQueue.tsx`

**Interfaces:**
- Consumes: `SEVERITIES`, `SEVERITY_COLOR_VAR`, `PILLAR_LABELS`, `PILLARS`,
  `PixelIcon` (Tasks 1, 2), `EmptyState` (Task 6).
- Produces: nothing new. Both keep their existing props. `FindingsTable` must
  keep `"Fix with your agent"` and `"Copied ✓"`.

- [ ] **Step 1: Write the failing test**

`frontend/src/test/FindingsTable.test.tsx` already exists and already pins
`"Fix with your agent"` and `"Copied ✓"`. Extend it with one pixel-specific
assertion rather than creating a new file:

Add to that file:

```tsx
  it("badges every severity from the shared ramp", async () => {
    // renders the fixture list, which contains one of each severity
    expect(document.querySelectorAll(".px-badge").length).toBeGreaterThan(1);
  });

  it("stipes alternate rows", () => {
    expect(document.querySelectorAll(".px-stripes").length).toBeGreaterThan(0);
  });
```

- [ ] **Step 2: Run the test to verify it fails**

```bash
cd frontend && npx vitest run src/test/FindingsTable.test.tsx
```
Expected: FAIL — no `.px-badge` or `.px-stripes` yet.

- [ ] **Step 3: Delete the duplicated maps in `FindingsTable.tsx`**

Remove `SEVERITY_STYLES` (lines ~10–17) and `PILLAR_LABELS` (lines ~43–51), and
import instead:

```tsx
import { PILLARS, PILLAR_LABELS, SEVERITIES, SEVERITY_COLOR_VAR } from "../lib/palette";
```

- [ ] **Step 4: Restyle the severity badge**

Replace the `rounded-md border px-1.5 py-0.5 text-[10px] font-bold uppercase tracking-wide ${SEVERITY_STYLES[...]}` element with:

```tsx
const severityColor = `var(${SEVERITY_COLOR_VAR[finding.severity]})`;
…
<span
  className="px-badge px-badge--flat"
  style={{ borderColor: severityColor, color: severityColor }}
>
  {finding.severity}
</span>
```

This is what deletes the third copy of `SEVERITY_STYLES` — the other two are
`ApprovalQueue` (Step 5) and `RemediationPlan` (Task 9).

- [ ] **Step 5: Restyle the rest of `FindingsTable.tsx`**

| current | new |
| --- | --- |
| `rounded-2xl border border-hairline bg-surface-2 px-4 py-8` no-match block | `<EmptyState title="No findings match" detail="Loosen the filter, or pick another pillar." />` |
| the two `select` filters | wrap each in `px-select-wrap`, add `<PixelIcon name="chevron-down" size={12} className="px-select-chevron" />` as a sibling |
| the pillar `select`'s option list | `PILLARS.map(...)` instead of `Object.entries(PILLAR_LABELS).map(...)` |
| `text-[10px] font-bold uppercase` severity legend | `px-eyebrow` |
| the `"Fix with your agent"` button | `px-btn px-btn--primary`, keep the accessible name |
| the copy button's `"Copied ✓"` | keep the string; put `<PixelIcon name="check" size={12} />` beside it |

Rows: give the wrapper `overflow-x-auto px-scroll` and apply `px-stripes` to odd
rows. Keep the group-by-severity structure and the 150-row cap.

- [ ] **Step 6: Restyle `ApprovalQueue.tsx`**

- delete its local `SEVERITY_STYLES` and import from `../lib/palette`
- `<span className="anim-pulse-soft h-1.5 w-1.5 rounded-full bg-warn" />` →
  `<span aria-hidden="true" className="anim-blink block h-[8px] w-[8px] bg-warn" />`
- the queue's `<p className="mt-3 text-sm text-faint">` empty state →
  `<EmptyState title="Nothing awaiting review" detail="High-severity agent claims land here for a human decision." />`
- the approve / dismiss buttons → `px-btn px-btn--primary` and `px-btn px-btn--ghost`
- the queue panel → `px-panel`, each item → `px-well`

Keep every string, including `GateBadge` labels — `ApprovalQueue` has no test
file, so any string change here is unforced; change nothing.

- [ ] **Step 7: Run the test, then the full suite**

```bash
cd frontend && npx vitest run src/test/FindingsTable.test.tsx
```
Expected: PASS, all tests including the two new ones.

```bash
cd frontend && npm run lint && npm run typecheck && npm test && npm run build
```

- [ ] **Step 8: Commit**

```bash
cd /home/krtk2/Docs/Projects/AI_Inteligence && git add frontend/src/components/FindingsTable.tsx frontend/src/components/ApprovalQueue.tsx frontend/src/test/FindingsTable.test.tsx
git commit -m "feat - a striped findings table badged from the shared severity ramp"
```

---

### Task 9: ExploreTab, RemediationPlan, AgentChat

**Files:**
- Modify: `frontend/src/components/ExploreTab.tsx`
- Modify: `frontend/src/components/RemediationPlan.tsx`
- Modify: `frontend/src/components/AgentChat.tsx`

**Interfaces:**
- Consumes: `PixelIcon`, `SEVERITY_COLOR_VAR`, `PILLAR_LABELS`, `Loading`,
  `EmptyState` (Tasks 1, 2, 6).
- Produces: nothing new. `RemediationPlan` must keep `"How to fix these issues"`,
  `"58 → 92"`, `"agent-authored"`, `"Download .md"`, `/show the steps/`,
  `/show 1 findings/`, `/Nothing to fix\. No open findings were recorded/`;
  `AgentChat` must keep `"Ask about this analysis…"`, `"Send"`,
  `"Reconnecting…"`, `"Reconnecting to the agent…"`,
  `/Requested from the fix plan/`.

- [ ] **Step 1: Establish the baseline**

```bash
cd frontend && npx vitest run src/test/RemediationPlan.test.tsx src/test/AgentChat.test.tsx
```
Expected: PASS on the current styling. If it is already red, stop and report.

- [ ] **Step 2: Restyle `ExploreTab.tsx`**

- `KindBadge` → `px-badge px-badge--flat` in `font-ui`, deleting its `rounded-*`
- `NeighborhoodPanel` → `px-panel`; its symbol rows → `px-well`
- `SymbolBrowser` rows → `px-card`, active row gets a 2px `--accent` left rule
- `<p className="mt-2 text-xs text-faint">` empty state →
  `<EmptyState title="No symbols" detail="This repository could not be indexed into a symbol graph." />`
- the three bare "Loading snippet… / Loading graph… / …" strings → `<Loading label="…" />`
- keep the 150-symbol cap and every existing label

- [ ] **Step 3: Restyle `RemediationPlan.tsx`**

This is the largest file (459 lines) and has the most pinned copy. Frame changes
only — do not restructure `PlanBody`, `WorkItemCard` or `referenceLabel`.

| current | new |
| --- | --- |
| `panel anim-rise p-6 sm:p-7` | `anim-step-in px-panel p-5` (×2 sites) |
| `rounded-2xl border border-hairline bg-surface-2 p-4` blocks | `px-well p-4` |
| `Show the steps` / `Hide the steps` buttons | `px-btn px-btn--ghost` |
| `Show N findings` buttons | `px-btn px-btn--ghost` |
| `Download .md` link | `px-link` with `<PixelIcon name="copy" size={12} />` beside it |
| `"agent-authored"` badge | `px-badge px-badge--flat` with `style={{ borderColor: "var(--hypo)", color: "var(--hypo)" }}` |
| local `SEVERITY_STYLES` and `PILLAR_LABELS` | delete; import from `../lib/palette`, and drive the badge off `SEVERITY_COLOR_VAR` |
| the `text-5xl` `58 → 92` projection | `font-ui text-[28px] tabular-nums`, current value in `--faint`, projected in `--ok`; keep the arrow |
| `"Nothing to fix."` block | `<EmptyState title="Nothing to fix" detail="No open findings were recorded." />` — the test regex is `/Nothing to fix\. No open findings were recorded/`, which no longer matches across two elements |

> That last row needs care: the pinned assertion is
> `screen.getByText(/Nothing to fix\. No open findings were recorded/)`, which
> requires **one contiguous text node**. Render it as
> `<EmptyState title="Nothing to fix. No open findings were recorded." />` and
> drop the `detail` prop. Do not split the sentence across two elements.

- [ ] **Step 4: Restyle `AgentChat.tsx`**

- the auth-error section `panel border-warn/30 bg-warn-soft p-5 text-sm text-warn`
  → `px-panel p-4 text-[13px] text-warn`, border `2px solid var(--warn)`
- the root `panel flex flex-col overflow-hidden` → `px-panel flex flex-col overflow-hidden`
- header: `border-b border-hairline` → `border-b-2 border-line`; `New chat` →
  `px-btn px-btn--ghost`
- tool chips → `px-badge px-badge--flat font-mono text-[9px]`
- transcript `max-h-96 … overflow-y-auto` → add `px-scroll`
- user message `rounded-2xl border border-accent/20 bg-accent-soft px-3.5 py-2 text-sm text-ink`
  → `px-well border-l-4 border-l-accent p-3 text-[13px] text-ink` — a left rule
  instead of a soft bubble
- the `dynamic-tool` glyphs `✓ ✗ ⊘ …` → `<PixelIcon name="check" | "cross" | "ban" | "chevron-down" size={12} />`,
  keeping the surrounding `text-ok/80` / `text-danger/80` / `text-warn/80` colours.
  **Exception:** if any string containing `✓` is asserted by a test, keep the
  literal character as well as the sprite. `AgentChat.test.tsx` asserts on
  `"Copied ✓"` in `FindingsTable`, not here, so this is safe — verify, do not assume.
- the approve button `bg-warn text-[#1a1205] hover:brightness-110` → replace the
  hardcoded hex with `px-btn px-btn--primary`; this removes the only hardcoded hex
  left in any `.tsx`
- composer: `input.input` → `px-input`; send button `btn btn-ink` → `px-btn px-btn--ink`,
  keeping the tri-state label `Reconnecting…` / `Working…` / `Send` and its `disabled`

- [ ] **Step 5: Verify no hardcoded hex remains in any `.tsx`**

```bash
cd frontend/src && grep -rnE '#[0-9a-fA-F]{3,8}\b' --include=*.tsx . || echo "OK: no literal hex in any tsx"
```
Expected: `OK`. This check is worth running in every task from here on — it is the
mechanical expression of constraint 1.

- [ ] **Step 6: Run the full suite**

```bash
cd frontend && npm run lint && npm run typecheck && npm test && npm run build
```
Expected: all pass, with `RemediationPlan.test.tsx` and `AgentChat.test.tsx`
green against the new copy.

- [ ] **Step 7: Commit**

```bash
cd /home/krtk2/Docs/Projects/AI_Inteligence && git add frontend/src/components/ExploreTab.tsx frontend/src/components/RemediationPlan.tsx frontend/src/components/AgentChat.tsx
git commit -m "feat - pixel the explorer, the fix plan and the agent chat"
```

---

### Task 10: The four pages

**Files:**
- Modify: `frontend/src/pages/DashboardPage.tsx`
- Modify: `frontend/src/pages/ReposPage.tsx`
- Modify: `frontend/src/pages/AnalysisDetailPage.tsx`
- Modify: `frontend/src/pages/LoginPage.tsx`

**Interfaces:**
- Consumes: everything above.
- Produces: nothing new. `AnalysisDetailPage`'s back link must keep
  `href="/"` and an accessible name matching `/back/i` — both pinned.

- [ ] **Step 1: Restyle `DashboardPage.tsx`**

- delete the local `scoreTone`; import it from `../lib/palette`. This is the copy
  that broke at 50 where `ScoreHero` broke at 40.
- the score numeral `text-2xl font-extrabold tabular-nums tracking-tight` →
  `font-ui text-[28px] tabular-nums`, wrapped in a `px-well px-3 py-1`
- `card card-hover flex items-center gap-4 px-4 py-3.5` →
  `px-card-hover flex items-center gap-4 p-3`
- repo name → `font-ui text-[11px] text-ink`; the subline →
  `font-mono text-[10px] text-faint`
- `Re-analyze` → `px-btn px-btn--ghost`
- the empty state → `<EmptyState title="No analyses yet" detail="Point Retract at a GitHub repository and it will score it." action={{ label: "Add a repository", to: "/repos" }} />`
- the error pill `rounded-2xl border border-danger/25 bg-danger-soft px-4 py-2.5 text-sm text-danger`
  → `<EmptyState title="Could not load your analyses" detail="Is the API running?" icon="cross" />`
- the Inventory count panel → `px-panel p-5`, count in `font-ui text-[28px]`

Keep the 3-second polling while any row is pending or running. It is behaviour,
not styling.

- [ ] **Step 2: Restyle `ReposPage.tsx`**

- `<h1 className="sr-only">` stays — it is the accessible page name
- the form's `bezel` / `bezel-core` → `px-frame p-4`
- the URL `input` → `px-input font-mono text-[12px]`
- `Analyze` / `Starting…` → `px-btn px-btn--primary`, label tri-state unchanged
- repo rows → `px-card-hover p-3`; `default_branch` stays `font-mono text-[11px]`
- `StatusPill` is already restyled; the row becomes a button via the existing
  click handler, so give it `aria-label` and keep keyboard activation

- [ ] **Step 3: Restyle `AnalysisDetailPage.tsx`**

- **header**: `px-panel p-5`
- **back link**: keep `href="/"` and the text `← Back`, styled `px-btn px-btn--quiet px-tab`
- **repo title** `text-2xl font-bold tracking-tight` → `font-ui text-[20px] font-bold`
- **the four stat tiles** `rounded-2xl border border-hairline bg-surface-2 px-3.5 py-2.5`
  → `px-well px-3 py-2`; labels `text-[10px] uppercase tracking-[0.18em] text-faint`
  → `px-eyebrow`
- **the segmented control**: Task 4 already rewired `.seg*` to `.px-tabs` /
  `.px-tab`, so this step's job is to replace the visual-only control with a real
  ARIA one. Delete the whole indicator block, its `tabIndex` math, the
  `style={{ transform: translateX(...) }}` and the `w-[calc(25%-0.125rem)]`
  width. Replace with:

  ```tsx
  <div role="tablist" aria-label="Analysis views" className="px-tabs">
    {(["overview", "explore", "fixes", "agent"] as const).map((value) => (
      <button
        key={value}
        role="tab"
        aria-selected={tab === value}
        onClick={() => setTab(value)}
        className="px-tab"
      >
        {value}
      </button>
    ))}
  </div>
  ```

  This is a real ARIA tablist rather than the old visual-only control. Give the
  panel `role="tabpanel"` if it costs nothing; it does not.
- **`ProgressFeed`**: `anim-rise` → `anim-step-in`; each row gets a `px-well` and
  an 8px square dot; add `px-scroll` to the list and cap it at `max-h-96`
- **`Loading…`, `Loading the agent…`, `Building the fix plan…`** Suspense
  fallbacks → `<Loading label="…" />`
- keep the SSE wiring, the 2-second polling, the score invalidation on `done`,
  and the tab order exactly as they are

- [ ] **Step 4: Restyle `LoginPage.tsx` — the pixel-art hero**

This is the page the spec calls for a "full pixel-art hero", so it gets the most
new markup.

Structure:

```tsx
<div className="grid min-h-[100dvh] place-items-center bg-canvas p-6">
  {/* Dithered sky behind the frame — a 2px checkerboard, not a gradient. */}
  <div aria-hidden="true" className="px-dither pointer-events-none fixed inset-0 opacity-30" />

  <div className="anim-step-in relative w-full max-w-[30rem]">
    <div className="px-frame">
      <div className="px-titlebar">
        <span className="flex items-center gap-2">
          <PixelIcon name="logo" size={10} className="text-accent" />
          RETRACT.EXE
        </span>
        <span className="ml-auto flex gap-1" aria-hidden="true">
          <span className="block h-[8px] w-[8px] bg-danger" />
          <span className="block h-[8px] w-[8px] bg-warn" />
          <span className="block h-[8px] w-[8px] bg-ok" />
        </span>
      </div>

      <div className="flex flex-col gap-4 p-5">
        <div className="flex items-center gap-4">
          {/* Two-frame blink: robot-open and robot-blink alternate. */}
          <span aria-hidden="true" className="anim-blink block text-accent">
            <PixelIcon name="robot-open" size={48} />
          </span>
          <div>
            <p className="px-eyebrow">Repository health</p>
            <h1 className="font-ui text-[20px] font-bold tracking-[0.18em] text-ink">
              RETRACT
            </h1>
          </div>
        </div>

        {/* Health bar: fills left to right in steps, then restarts. */}
        <div>
          <p className="px-eyebrow mb-1">System health</p>
          <span className="anim-slide-up flex gap-[2px] border-2 border-line bg-canvas p-[2px]">
            {Array.from({ length: 20 }, (_, index) => (
              <span
                key={index}
                className="block h-[8px] w-[8px]"
                style={{ background: index < 13 ? "var(--ok)" : "var(--line-strong)", opacity: index < 13 ? 1 : 0.35 }}
              />
            ))}
          </span>
        </div>

        <p className="text-[13px] leading-relaxed text-muted">
          Give it a GitHub repository. Get back a health score with verified,
          cited findings.
        </p>

        {/* banners, GitHub button, ASCII rule, tabs, email form — unchanged copy */}
      </div>
    </div>
  </div>
</div>
```

Inside that frame, replace the remaining old-style pieces:

| current | new |
| --- | --- |
| the segmented sign-in / create-account control | two `.px-tab`s inside `role="tablist"`; delete the sliding indicator, its `w-[calc(50%-0.25rem)]` width and `translateX(100%)` transform |
| `h-px flex-1 bg-hairline` dividers | `px-rule` |
| `btn btn-ink w-full gap-2` GitHub button | `px-btn px-btn--ink w-full` + `<PixelIcon name="github" size={12} />` |
| `btn btn-primary` submit | `px-btn px-btn--primary w-full` |
| the dev-login button | `px-btn px-btn--ghost w-full` |
| `btn btn-ghost` theme toggle in the corner | unchanged from Task 5 |
| `text-xs text-faint` footer microcopy | `font-mono text-[10px] text-faint` |

**Keep, unchanged** — every one is pinned by `LoginPage.test.tsx`: the
`aria-label="Email sign-in"` form, `"Sign in with GitHub"` and its
`href="/api/auth/github/login"`, `"Dev login"`, the `"you@example.com"` and
`"Password"` / `"At least 8 characters"` placeholders, the `"Sign in"` /
`"Create account"` button labels, the `emailVerified` and `error` banners, and
all six `AUTH_ERRORS` strings. The `import.meta.env.DEV` gate on dev login
stays.

- [ ] **Step 5: Verify the migration is fully closed out**

```bash
cd frontend/src && for token in hairline "solid" "glass-pill" "anim-rise" "ease-glide" "rounded-"; do
  printf '%-14s ' "$token"
  if grep -rq "$token" --include=*.tsx .; then echo "STILL PRESENT"; else echo "clean"; fi
done
cd frontend/src && grep -rnE '#[0-9a-fA-F]{3,8}\b' --include=*.tsx . || echo "OK: no literal hex in any tsx"
```
Expected: every `clean`, then `OK`.

```bash
cd frontend/src && grep -c "bezel\|seg-indicator" --include=*.tsx -r . || echo "OK: legacy shell classes gone"
```

- [ ] **Step 6: Run the full check suite**

```bash
cd frontend && npm run lint && npm run typecheck && npm test && npm run build
```

- [ ] **Step 7: Commit**

```bash
cd /home/krtk2/Docs/Projects/AI_Inteligence && git add frontend/src/pages/
git commit -m "feat - pixel the dashboard, repositories, analysis workspace and login"
```

---

### Task 11: Visual verification and final sweep

**Files:**
- Modify: whatever the pass surfaces.

**Interfaces:**
- Consumes: the whole redesign.
- Produces: the confirmation that the thing actually looks like the spec, which
  no test can tell you.

- [ ] **Step 1: Start the stack**

```bash
cd frontend && npm run dev
```
If the API and agent are not running, start them too — `bash scripts/dev-local.sh start`
from the repo root, with Node 24 on PATH.

- [ ] **Step 2: Screenshot every screen in both themes**

Walk: `/` → `/repos` → an analysis detail page (all four tabs) → log out →
login. For each, capture dark and light. Use the `webapp-testing` or
`agent-browser` skill.

- [ ] **Step 3: Check the specific things a screenshot catches that a test cannot**

- no circle anywhere — anything still round means a `rounded-*` survived
- no blur or glow anywhere
- the scanlines are visible but text is not degraded by them
- every focus ring is visible, including on `--accent` fills
- the pillar meters, coverage bar and acceptance bars all read as one instrument
- the "not measured" pillar is visibly *different* from both 0 and 100
- the score ring segments land on whole pixels at the rendered size
- light mode: all six pillar hues and all five severities are distinguishable
- the sidebar stays put while content scrolls, and the title bar stays put while
  the sidebar scrolls

- [ ] **Step 4: Check keyboard traversal end to end**

Tab from the top of the login page. Every stop must have a visible 2px ring.
Enter must work on every control the mouse works on — the sidebar tabs, the
analysis tabs, the segmented login control.

- [ ] **Step 5: Run the whole project's checks, not just the frontend's**

```bash
cd frontend && npm run lint && npm run typecheck && npm test && npm run build
cd ../backend && ruff check . && ruff format --check . && mypy && python -m pytest
```
The backend must be untouched and green; if it is not, something outside this
plan edited it.

- [ ] **Step 6: Fix what the pass surfaced, one commit per fix**

- [ ] **Step 7: Update the README**

The README describes the stack, not the design, so it needs no change — but add
one line to the `Layout` bullet in the Layout section of the root README noting
the UI is a PICO-8 pixel system with a window-chrome shell, so the next reader
knows the visual language is deliberate and not an accident:

```markdown
- `frontend/` — React + Vite dashboard; PICO-8 pixel UI, window chrome + sidebar
```

- [ ] **Step 8: Commit**

```bash
cd /home/krtk2/Docs/Projects/AI_Inteligence
# stage only the files the visual pass actually touched, then:
git commit -m "fix - whatever the visual pass surfaced"
```

---

## Appendix A — Complete token reference

Every custom property the plan introduces, with both themes. Copy from this, not
from memory.

| property | light | dark |
| --- | --- | --- |
| `--canvas` | `#c2c3c7` | `#000000` |
| `--surface` | `#fff1e8` | `#1d2b53` |
| `--surface-2` | `#c2c3c7` | `#000000` |
| `--line` | `#5f574f` | `#5f574f` |
| `--line-strong` | `#1d2b53` | `#c2c3c7` |
| `--ink` | `#000000` | `#fff1e8` |
| `--muted` | `#5f574f` | `#c2c3c7` |
| `--faint` | `#83769c` | `#83769c` |
| `--accent` | `#1d2b53` | `#29adff` |
| `--accent-strong` | `#7e2553` | `#ffec27` |
| `--accent-ink` | `#fff1e8` | `#000000` |
| `--ok` | `#008751` | `#00e436` |
| `--warn` | `#ab5236` | `#ffa300` |
| `--danger` | `#ff004d` | `#ff004d` |
| `--info` | `#1d2b53` | `#ffec27` |
| `--hypo` | `#7e2553` | `#ff77a8` |
| `--shadow` | `#5f574f` | `#000000` |
| `--bevel-hi` | `rgba(255,255,255,.55)` | `rgba(255,241,232,.1)` |
| `--bevel-lo` | `rgba(0,0,0,.3)` | `rgba(0,0,0,.55)` |
| `--accent-soft` | `mix(accent 22%, surface)` | same |
| `--ok-soft` | `mix(ok 22%, surface)` | same |
| `--warn-soft` | `mix(warn 22%, surface)` | same |
| `--danger-soft` | `mix(danger 22%, surface)` | same |
| `--info-soft` | `mix(info 22%, surface)` | same |
| `--hypo-soft` | `mix(hypo 22%, surface)` | same |
| `--px-border` | `2px` | `2px` |
| `--px-offset` | `4px` | `4px` |
| `--px-cell` | `8px` | `8px` |
| `--pillar-security` | `#ff004d` | `#ff004d` |
| `--pillar-code-quality` | `#ab5236` | `#ffa300` |
| `--pillar-testing` | `#1d2b53` | `#29adff` |
| `--pillar-architecture` | `#7e2553` | `#83769c` |
| `--pillar-documentation` | `#008751` | `#ff77a8` |
| `--pillar-dependencies` | `#5f574f` | `#00e436` |
| `--sev-critical` | `#ff004d` | `#ff004d` |
| `--sev-high` | `#ab5236` | `#ffa300` |
| `--sev-medium` | `#7e2553` | `#ffec27` |
| `--sev-low` | `#1d2b53` | `#29adff` |
| `--sev-info` | `#5f574f` | `#c2c3c7` |
| `--status-pending` | `#5f574f` | `#83769c` |
| `--status-running` | `#ab5236` | `#ffec27` |
| `--status-done` | `#008751` | `#00e436` |
| `--status-failed` | `#ff004d` | `#ff004d` |
| `--ease-step` | `steps(3, end)` | same |
| `--font-sans` | Pixelify Sans | same |
| `--font-ui` | Silkscreen | same |
| `--font-mono` | JetBrains Mono | same |

## Appendix B — Where the old design's names went

| old class | why it is gone |
| --- | --- |
| `panel` → `px-panel` | kept, reimplemented |
| `card`, `card-hover` → `px-card`, `px-card-hover` | hover moved to a sibling class because a shadow-less card and a shadowed card are different things |
| `bezel`, `bezel-core` → `px-frame` | the double-bezel was frosted-glass language; a window frame is one border and a hard shadow |
| `glass-pill` | the floating capsule header is a title bar now |
| `seg`, `seg-item`, `seg-indicator` → `px-tabs`, `px-tab` | a sliding rounded pill cannot be a 2px underline rule |
| `hairline` → `line`, `hairline-strong` → `line-strong` | "hairline" described a 1px translucent border; these are 2px solid ones |
| `solid` → `surface` | `--solid` existed only as the donut's inner disc |
| `anim-rise` → `anim-step-in` | the old one blurred and scaled; this one steps |
| `anim-pulse-soft` → `anim-blink` | opacity easing became opacity stepping |
| `ease-glide` → `ease-step` | `cubic-bezier(0.32,0.72,0,1)` is a smooth glide; nothing glides now |
| `--accent-glow`, `--accent-glow-soft`, `--shadow-tint`, `--grain-*`, `--aurora-*`, `--hairline-inner` | glow, tint and grain are all effects the pixel system does not have |
| `anim-float` | declared, never used, and never would be here |