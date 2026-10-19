# Instrument Console Implementation Plan

> **For agentic workers:** steps use `- [ ]` checkboxes. Verify every task with
> `cd frontend && npm run lint && npm run typecheck && npm test && npm run build`.

**Goal:** Replace the PICO-8 pixel UI with an instrument-console design system —
new tokens, new primitives, a top-bar + nav-rail shell, and every page and
component restyled. Both themes co-equal, teal accent, Geist typography.

**Spec:** `docs/superpowers/specs/2026-10-17-instrument-console-design.md`

**Constraints**

1. No new npm dependencies. Fonts are a Google Fonts `<link>` in `index.html`.
2. Colour values live only in `index.css` and `lib/palette.ts`.
3. A `.` component owns its own padding, font-size and font-weight; never put a
   conflicting Tailwind utility beside one.
4. No new user-visible strings where a test pins one (spec §7).
5. `api/*`, `lib/theme.ts`, `lib/clipboard.ts`, `lib/buildFixPrompt.ts`,
   `ThemeProvider`, auth and SSE are untouched.

## Class migration (the whole contract)

| old | new |
| --- | --- |
| `px-panel`, `px-frame` | `panel` (`frame` for the login card) |
| `px-card`, `px-card-hover` | `card`, `card card--hover` |
| `px-well` | `inset` |
| `px-titlebar` | `topbar` |
| `px-eyebrow` | `eyebrow` |
| `px-btn` | `btn` |
| `px-btn--primary/ghost/quiet/danger/ink` | `btn--primary/ghost/quiet/danger/solid` |
| `px-btn-icon` | `btn--icon` |
| `px-input` | `input` |
| `px-input px-select` | `input select` |
| `px-select-wrap` / `px-select-chevron` | `select-wrap` / `select-chevron` |
| `px-badge`, `px-badge--flat` | `chip`, `chip chip--flat` |
| `px-tabs`, `px-tab`, `px-tab--side`, `px-tab-active` | `tabs`, `tab`, `tab--side`, `tab-active` |
| `px-rule` | `rule` |
| `px-scroll` | `scroll` |
| `px-link` | `link` |
| `px-skip` | `skip` |
| `px-dither`, `px-stripes` | `skeleton`, `stripes` |
| `anim-step-in`, `anim-blink`, `anim-slide-up` | `anim-in`, `anim-pulse` |

## Files

**Rewritten:** `index.css`, `index.html`, `components/Layout.tsx`,
`components/ThemeToggle.tsx`.
**Created:** `components/Icon.tsx`, `components/Sparkline.tsx`,
`test/Icon.test.tsx`, `test/Sparkline.test.tsx`.
**Deleted:** `components/PixelIcon.tsx`, `test/PixelIcon.test.tsx`.
**Restyled:** `App.tsx`, `StatusPill`, `EmptyState`, `ScoreHero`,
`VerifyEmailBanner`, `DashboardPage`, `ReposPage`, `LoginPage`,
`AnalysisDetailPage`, `FindingsTable`, `ApprovalQueue`, `TrustPanel`,
`HistoryCompare`, `ExploreTab`, `RemediationPlan`, `AgentChat`; `lib/palette.ts`
values.

## Tasks

- [x] **1. Foundation** — rewrite `index.css` (tokens + primitives), new
  `palette.ts` values, `Icon.tsx`, new `Meter`/`ScoreRing`/`Sparkline`,
  `index.html` fonts + favicon.
- [x] **2. Shell** — `Layout` top bar + nav rail, `ThemeToggle`, `App` splash,
  `EmptyState` (`skeleton`), `StatusPill` (`chip`).
- [x] **3. Screens** — `ScoreHero`, `VerifyEmailBanner`, `DashboardPage`,
  `ReposPage`, `LoginPage`, `AnalysisDetailPage`, `FindingsTable`,
  `ApprovalQueue`, `TrustPanel`, `HistoryCompare`, `ExploreTab`,
  `RemediationPlan`, `AgentChat`.
- [x] **4. Tests & docs** — update the six pinning tests, add `Icon`/`Sparkline`
  tests, update the README layout line.
