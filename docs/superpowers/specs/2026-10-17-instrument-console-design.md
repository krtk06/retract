# Instrument Console redesign

Date: 2026-10-17
Scope: `frontend/` — shell, tokens, primitives and every page/component.
Status: approved design, implemented.
Supersedes: `2026-10-17-pixel-ui-redesign-design.md` (the PICO-8 pixel system).

## 1. What this replaces

The app today is a PICO-8 pixel system: a pure-black canvas, 16-colour palette,
2px hard borders, hard offset shadows, scanlines, dither, `border-radius: 0`
everywhere, Silkscreen/Pixelify Sans typography and `steps()` motion. It is
distinctive, but for a tool whose pitch is **"computed, not vibes"** plus
verification of security findings, the arcade register reads playful where the
product needs to read forensic. Silkscreen at 9px is also a real legibility tax
on the findings table and the agent transcript.

This design replaces it with an **instrument console**: the Linear / Sentry /
Datadog register. Precise, calm, dense, data-forward. Depth comes from layered
surfaces and hairline borders — not glass, gradients, glow or hard pixel shadows.
Colour is a signal, not decoration: neutral UI, one teal accent, semantics
reserved for meaning.

### Non-goals

- No new features, routes, API calls, or data. Presentational only.
- No new npm dependencies. Fonts are a Google Fonts `<link>`.
- No change to the eve agent contract, SSE handling, react-query hooks, or auth.
- No change to any user-visible string a test pins (see §7).

## 2. Palette

Dark is the default; light is co-equal, not a fallback.

| token | dark | light |
| --- | --- | --- |
| `--canvas` | `#0b0d10` | `#f7f8fa` |
| `--surface` | `#111418` | `#ffffff` |
| `--surface-2` | `#171b21` | `#f1f3f5` |
| `--surface-3` | `#1e242c` | `#ffffff` |
| `--line` | `#262c34` | `#e4e7eb` |
| `--line-strong` | `#3a424d` | `#cdd2d9` |
| `--ink` | `#e6e9ed` | `#111418` |
| `--muted` | `#9ba3ae` | `#4b5563` |
| `--faint` | `#6b7280` | `#9aa1ac` |
| `--accent` | `#2dd4bf` | `#0d9488` |
| `--accent-strong` | `#14b8a6` | `#0f766e` |
| `--accent-ink` | `#04211e` | `#ffffff` |
| `--ok` | `#12b76a` | `#067647` |
| `--warn` | `#f79009` | `#b54708` |
| `--danger` | `#f04438` | `#d92d20` |
| `--info` | `#4c8dff` | `#175cd3` |
| `--hypo` | `#a78bfa` | `#7c3aed` |

`--*-soft` tints remain `color-mix(in srgb, var(--x) 16%, var(--surface))`.

### 2.1 Severity ramp (warm = worse)

| severity | dark | light |
| --- | --- | --- |
| critical | `#f04438` | `#d92d20` |
| high | `#f79009` | `#b54708` |
| medium | `#f5b547` | `#b45309` |
| low | `#4c8dff` | `#175cd3` |
| info | `#98a2b3` | `#667085` |

### 2.2 Pillars

| pillar | dark | light |
| --- | --- | --- |
| security | `#f04438` | `#d92d20` |
| code-quality | `#f79009` | `#b54708` |
| testing | `#4c8dff` | `#175cd3` |
| architecture | `#a78bfa` | `#7c3aed` |
| documentation | `#f472b6` | `#db2777` |
| dependencies | `#12b76a` | `#067647` |

### 2.3 Status

| status | dark | light |
| --- | --- | --- |
| pending | `#98a2b3` | `#667085` |
| running | `#f5b547` | `#b54708` |
| done | `#12b76a` | `#067647` |
| failed | `#f04438` | `#d92d20` |

### 2.4 Score thresholds

One table, unchanged: `>=80 ok, >=60 info, >=40 warn, else danger`.

## 3. Typography

| role | family |
| --- | --- |
| UI + prose | **Geist** |
| code, paths, SHAs, metrics | **Geist Mono** |

Scale: 12/13/14 body, 16/20/28 headings, 32–56 display score. Line-height
1.5–1.65 for prose. `tabular-nums` on every number. Silkscreen/Pixelify Sans are
removed.

## 4. Geometry, depth, motion

- Radius: 6px controls, 8px inset, 10px panels/cards, 12px frame, 999px chips.
- Depth: hairline 1px borders first; overlays only get one soft shadow
  (`0 8px 24px rgba(0,0,0,.28)` dark / `0 8px 24px rgba(16,24,40,.10)` light).
- Motion: one curve `cubic-bezier(0.16,1,0.3,1)`, 120–240ms. `transform`/
  `opacity` only. `prefers-reduced-motion` block retained.
- Background: flat `--canvas`. No scanlines, no dot grid, no dither.

## 5. Primitives

~20 classes replace the `px-*` set. Shared metrics: 1px borders, 6/8/10/12px
radii.

| class | definition |
| --- | --- |
| `.panel` | `bg-surface`, 1px `--line`, 10px radius |
| `.card` | `.panel` for list rows; `.card--hover` adds a surface-2 hover |
| `.inset` | `bg-surface-2`, 1px `--line`, 8px radius |
| `.frame` | 12px radius + soft shadow — the login card |
| `.topbar` | 48px sticky bar, translucent surface + `backdrop-blur` |
| `.eyebrow` | 11px uppercase tracking, `--faint` |
| `.btn` | 32px, 1px border, 6px radius; `.btn--primary/ghost/quiet/danger/solid/icon` |
| `.input` | 34px, `bg-surface-2`, 6px radius; `.select` adds a chevron slot |
| `.chip` | 999px pill, 1px border; `.chip--flat` drops the fill |
| `.tabs`/`.tab`/`.tab--side` | underline indicator on the active tab |
| `.rule` | 1px `--line` divider |
| `.skeleton` | shimmer block for loading rows |
| `.stripes` | subtle `--surface-2` row banding |
| `.scroll` | slim themed scrollbar |
| `.link`, `.skip` | accent link, focus skip target |
| `.anim-in`, `.anim-pulse` | fade-up entrance, live pulse |

### 5.1 Meters

`Meter` becomes a proportional track + fill (5% is no longer a cell). `null`
renders a hatched track and an em dash — "nobody measured this" is still not a
value. `ScoreRing` becomes a smooth SVG arc gauge with the numeral centred.
New `Sparkline` draws a run-over-run trend line where history exists.

### 5.2 Icons

`PixelIcon` (grid strings) is replaced by `Icon.tsx`: ~18 crisp 1.5px-stroke SVG
paths, `currentColor`, decorative unless given a title. No new dependency.

## 6. Layout and screens

```
┌──────────────────────────────────────────────────────────┐
│ ◉ RETRACT   [nav: Dashboard · Repositories]   ☾  user  ⏻ │ 48px, sticky
├────────────┬─────────────────────────────────────────────┤
│ DASHBOARD  │  content, max 1120px, document scroll        │
│ REPOSITORY │                                             │
│ ────────── │                                             │
│ user card  │                                             │
└────────────┴─────────────────────────────────────────────┘
```

- **Top bar**: logo sprite + wordmark, the nav as inline tabs, then theme toggle,
  user and a labelled log-out control.
- **Nav rail**: 232px, sticky under the bar, its own scroll; a 2px accent left
  rule marks the active route; a user card closes it.
- **Below `lg`**: the rail collapses to a horizontal tab strip under the bar. No
  drawer.
- **Scroll**: document scrolls; the rail scrolls independently; no third nested
  region is added.

Screens are restyled, not restructured: Dashboard, Repositories, Analysis
workspace (header + Overview/Explore/Fixes/Agent tabs) and Login. Analysis tab
order and page composition are unchanged. Login drops the `RETRACT.EXE` window
chrome and robot sprite for an `app frame` card with the brand lockup, the
GitHub button and the email form.

## 7. Tests

Tests query by role/text, except these which pin names and must be updated in the
same commit as the change they assert:

| test | pinned | action |
| --- | --- | --- |
| `palette.test.ts` | PICO-8 hex set | assert the new set |
| `Meter.test.tsx` | `[data-lit]`, `.px-dither` | rewrite for track + gauge |
| `PixelIcon.test.tsx` | `ICONS`, `crispEdges` | replace with `Icon.test.tsx` |
| `EmptyState.test.tsx` | `.px-dither` rows | assert `.skeleton` |
| `Layout.test.tsx` | `.px-titlebar`, window dots | assert `.topbar`, nav, skip link |
| `FindingsTable.test.tsx` | `.px-badge`, `.px-stripes` | assert `.chip`, `.stripes` |

Pinned copy that must survive (from `ScoreHero`, `RemediationPlan`, `AgentChat`,
`LoginPage`, `FindingsTable`, `VerifyEmailBanner`, `AnalysisDetailPage`) is
unchanged. New tests: `Icon.test.tsx`, `Sparkline.test.tsx`.

## 8. Risks

| risk | mitigation |
| --- | --- |
| Class rename touches every component | one migration table; verify lint/typecheck/test/build per pass |
| Component padding/type overridden by utilities | a `*.component` owns its padding and type; no conflicting utilities beside it |
| Two themes drift | every colour is a token with both values; `palette.test.ts` fails on an unassigned slot |
| Removing the pixel identity is a taste call | the change is isolated to `index.css` + `palette.ts`; a revert is a two-file diff |
