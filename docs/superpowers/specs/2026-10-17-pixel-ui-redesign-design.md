# Pixel UI redesign

Date: 2026-10-17
Scope: `frontend/` — every page, component, token and layout.
Status: approved design, not yet implemented.

## 1. What this replaces

The app today is a dark emerald "aurora glass" system: translucent frosted panels
with `backdrop-filter: blur(22px)`, a drifting three-stop aurora gradient, film
grain, `rounded-full` on 27 elements, Plus Jakarta Sans for prose, and a single
glowing orb as the logo. It is soft, glassy, and calm.

This design replaces all of it. The new system is **hard-edged, blocky, and
strictly limited to the 16 PICO-8 colours**, in the spirit of a well-made 8-bit
dev tool rather than an arcade pastiche: pixel geometry and pixel typography, but
a body font chosen for actual readability, because the findings table and the
agent transcript are text-heavy.

### Non-goals

- No new features, routes, API calls, or data. This is presentational only.
- No component library. Nothing is added to `package.json` except Google Fonts.
- No change to the eve agent contract, SSE handling, react-query hooks, or auth.
- No change to any user-visible string that a test pins (see §9).

## 2. Palette

Only the 16 canonical PICO-8 colours appear anywhere in the UI.

```
 0 #000000 black        4 #AB5236 brown        8 #FF004D red       12 #29ADFF blue
 1 #1D2B53 dark blue    5 #5F574F dark grey   9 #FFA300 orange    13 #83769C lavender
 2 #7E2553 dark purple  6 #C2C3C7 light grey  10 #FFEC27 yellow    14 #FF77A8 pink
 3 #008751 dark green   7 #FFF1E8 white      11 #00E436 green     15 #FFCCAA peach
```

Hierarchy does **not** come from new shades. It comes from three devices only:
**opacity** (a 45% white text is still white), **dither** (a 2px checkerboard of
two palette entries, exactly how PICO-8 shades art), and **surface depth** (fill
swap + bevel).

### 2.1 Semantic tokens

Dark is the default theme.

| token | dark | light | note |
| --- | --- | --- | --- |
| `--canvas` | `#000000` | `#C2C3C7` | page background |
| `--surface` | `#1D2B53` | `#FFF1E8` | panels, cards, title bar |
| `--surface-2` | `#000000` | `#C2C3C7` | sunken wells, nested blocks |
| `--line` | `#5F574F` | `#5F574F` | 2px borders and dividers |
| `--line-strong` | `#C2C3C7` | `#1D2B53` | emphasis borders, meter empty cells |
| `--ink` | `#FFF1E8` | `#000000` | primary text |
| `--muted` | `#C2C3C7` | `#5F574F` | secondary text |
| `--faint` | `#83769C` | `#83769C` | tertiary text, disabled |
| `--accent` | `#29ADFF` | `#1D2B53` | primary action, focus, links |
| `--accent-strong` | `#FFEC27` | `#7E2553` | hover, 100% meter cell |
| `--accent-ink` | `#000000` | `#FFF1E8` | text on accent |
| `--ok` | `#00E436` | `#008751` | passed, done, verified |
| `--warn` | `#FFA300` | `#AB5236` | pending review, degraded |
| `--danger` | `#FF004D` | `#FF004D` | failed, critical, secrets |
| `--info` | `#FFEC27` | `#1D2B53` | neutral system message |
| `--hypo` | `#FF77A8` | `#7E2553` | unverified agent hypothesis |
| `--shadow` | `#000000` | `#5F574F` | hard offset shadows |
| `--bevel-hi` | `rgba(255,241,232,0.10)` | `rgba(255,255,255,0.55)` | inset highlight |
| `--bevel-lo` | `rgba(0,0,0,0.55)` | `rgba(0,0,0,0.30)` | inset shadow |

`--bevel-hi`/`--bevel-lo` are the only non-palette values, and they exist solely
so the inset bevel reads on both themes.

### 2.2 Severity is a magnitude ramp

Warm means worse. Learned once, applied everywhere:

| severity | dark | light |
| --- | --- | --- |
| critical | `#FF004D` | `#FF004D` |
| high | `#FFA300` | `#AB5236` |
| medium | `#FFEC27` | `#7E2553` |
| low | `#29ADFF` | `#1D2B53` |
| info | `#C2C3C7` | `#5F574F` |

Light mode has no yellow that survives on cream, so its medium step moves into
the purple. The ramp stays monotonic in warmth, which is the property that
carries the meaning.

### 2.3 Pillars

Six distinct hues, in both themes:

| pillar | dark | light |
| --- | --- | --- |
| security | `#FF004D` | `#FF004D` |
| code-quality | `#FFA300` | `#AB5236` |
| testing | `#29ADFF` | `#1D2B53` |
| architecture | `#83769C` | `#7E2553` |
| documentation | `#FF77A8` | `#008751` |
| dependencies | `#00E436` | `#5F574F` |

Pillar hues deliberately overlap the severity hues. The two never appear in the
same context — pillars as labelled meter rows, severities as badges — and sharing
a language keeps the palette at 16 instead of needing 22 colours.

### 2.4 Score thresholds

One table, replacing three. Today `DashboardPage.scoreTone` breaks at
80/60/**50** and `ScoreHero.tone` at 80/60/**40**, so the same score is two
colours in two places.

```
>= 80  ok        #00E436 / #008751
>= 60  info      #29ADFF / #1D2B53
>= 40  warn      #FFA300 / #AB5236
else   danger    #FF004D / #FF004D
```

## 3. Typography

Three families, four roles. Two of the three are already vendored or standard
Google Fonts; none is a new dependency beyond the font link.

| role | family | weights | applies to |
| --- | --- | --- | --- |
| UI | **Silkscreen** | 400, 700 | headings, buttons, badges, table heads, nav, tabs, **all numbers** |
| prose | **Pixelify Sans** | 400, 500, 600, 700 | finding descriptions, chat transcript, plan text, empty states |
| code | **JetBrains Mono** | 400, 500 | file paths, SHAs, symbol names, tool names, event log |

The wordmark is `RETRACT` in Silkscreen 700, uppercase, `letter-spacing: 0.18em`.
No fourth family.

**Silkscreen never renders prose.** It has a small x-height and its lowercase
forms are near-unicase; at paragraph length it is hostile. This is the single
most important typographic decision in the redesign.

### 3.1 Scale

| role | size / weight / family |
| --- | --- |
| wordmark | 13px / 700 / Silkscreen / 0.18em |
| page title | 20px / 700 / Silkscreen |
| panel title | 13px / 700 / Silkscreen |
| eyebrow (`.eyebrow`) | 9px / 400 / Silkscreen / 0.16em / uppercase |
| badge | 9px / 700 / Silkscreen / 0.06em / uppercase |
| body | 13px / 400 / Pixelify Sans / 1.65 |
| meta | 11px / 400 / Pixelify Sans |
| code | 11px / 400 / JetBrains Mono |
| display score | 44px / 700 / Silkscreen / `tabular-nums` |

## 4. Pixel primitives

Every `border-radius` in the app becomes `0`. Every `backdrop-filter`, `blur()`,
soft `box-shadow`, and colour gradient is removed. These ~20 classes replace the
22 that exist today.

Shared metrics:

```
--px-border:  2px    every border width
--px-offset:  4px    standard hard shadow offset (3px on buttons, 2px on badges)
--px-cell:    8px    meter cell width, dot-grid unit
```

| class | definition |
| --- | --- |
| `.px-frame` | 2px `--line` border, 4px hard shadow, `bg-canvas` |
| `.px-titlebar` | h-28px, 2px bottom border, `bg-surface`, Silkscreen content |
| `.px-panel` | `bg-surface`, 2px `--line`, `4px 4px 0 0 var(--shadow)` |
| `.px-card` | `.px-panel` without the shadow — list rows |
| `.px-well` | `bg-surface-2`, 2px `--line`, `inset 2px 2px 0 var(--bevel-lo)` + `inset -2px -2px 0 var(--bevel-hi)` |
| `.px-btn` | 2px border, 3px offset shadow; `:active` → `translate(2px,2px)` + `1px 1px 0` shadow |
| `.px-btn--primary` | `--accent` fill, `--accent-ink` text |
| `.px-btn--ghost` | transparent fill, `--line` border |
| `.px-btn--quiet` | no fill, no border, `--muted` text |
| `.px-btn--danger` | `--danger` fill |
| `.px-btn[disabled]` | `--dither` background, `--faint` text, no shadow, no press |
| `.px-input` | `.px-well` + 2px `--line`; `:focus-visible` → 2px `--accent` inset ring, square caret |
| `.px-badge` | 2px border, 2px shadow, 9px Silkscreen uppercase |
| `.px-badge--flat` | no shadow — for badges inside list rows |
| `.px-meter` | flex row of 20 `--px-cell` squares |
| `.px-ring` | SVG segmented gauge, `shape-rendering: crispEdges` |
| `.px-tab` | relative button; active gets a 2px `--accent` bottom rule |
| `.px-rule` | 2px `--line` divider |
| `.px-scroll` | 12px square scrollbar, `--surface-2` track, `--line-strong` thumb |
| `.px-dither` | 2px `repeating-conic-gradient` checkerboard of two palette entries |
| `.px-stripes` | 1px dither, for table row striping |
| `.anim-step-in` | `steps(3)` entrance, 4px translate, no blur, no scale |
| `.anim-blink` | `steps(2)` opacity blink, for live/pending indicators |

### 4.1 The meter system

One 20-cell unit, 5% per cell, shared by four displays so they read as one
instrument rather than four unrelated bars:

- the score ring (radial, §4.2)
- the six pillar meters in `ScoreHero`
- verification coverage in `TrustPanel`
- human acceptance by category in `TrustPanel`

A pillar with **zero findings** renders its 20 cells as a 2px `.px-dither`
pattern and shows an em-dash instead of a score, exactly as today. It must not
render as a solid or empty bar, because "nobody measured this" is not a value.

### 4.2 Score ring

The smooth `conic-gradient` donut becomes a blocky ring of **20 rectangles**,
each 6×10px with a 2px gap, positioned by `transform: rotate(Ndeg) translateY(-R)`
around the centre, in an SVG with `shape-rendering: crispEdges"`. Filled cells
take the score tone, empty cells take `--line-strong` at 40%.

`AnimatedNumber` counts in `steps(10)` so digits snap like a mechanical counter.

### 4.3 Pixel icons

New `PixelIcon.tsx`. Icons are declared as grid strings — `#` is ink, `.` is transparent — and
rendered as SVG `rect`s:

```ts
const CHEVRON_DOWN = [
  "100000001",
  "110000011",
  "111000111",
  "111111111",
  "011111110",
  "001111100",
  "000111000",
  "000010000",
  "000000000",
];
```

Sized to 8 or 16px on a 10px or 16px grid, `shape-rendering: crispEdges`, current
colour. Every grid string must be rectangular and binary; `PixelIcon.test.ts`
enforces both. Replaces: `SunIcon`, `MoonIcon`, `GitHubMark`, the select chevron
(which leaves the CSS data-URI and becomes a `PixelIcon`), and the decorative
glyphs currently typed inline (`✓ ✗ ⊘ ▲ ▼ →` become sprites, except where a test
pins them).

### 4.4 Background

The aurora and the film grain are removed. What remains, in order:

1. `--canvas` flat fill
2. 8px dot grid, `--line` at 6% opacity — the `--px-cell` unit reused
3. 2px scanlines, black at 4% opacity, always on, `position: fixed`, `pointer-events: none`
4. radial vignette, black at 25% at the corners

No animation on the backdrop. A drifting background fought with every meter.

### 4.5 Motion

| today | new |
| --- | --- |
| `rise` — 18px translate + `blur(6px)` + scale | `anim-step-in` — 4px translate, `steps(3)`, no blur |
| `pulse-soft` — opacity ease-in-out | `anim-blink` — opacity `steps(2)` |
| score count-up, cubic ease-out | score count-up, `steps(10)` |
| pillar bar width, 800ms ease-glide | pillar cells, `steps(20)` |
| orb glow, 46s aurora drift | none |

The existing `prefers-reduced-motion` block stays and still neutralises
everything.

## 5. Layout

```
┌────────────────────────────────────────────────────────────────┐
│ ▪ RETRACT   DASHBOARD · REPOSITORIES   ● ● ●   ☾  krztk2  [LOG OUT]│ 28px title bar, sticky
├──────────────┬─────────────────────────────────────────────────┤
│ DASHBOARD    │                                                 │
│ REPOSITORIES │   content, max 1120px, document scroll           │
│ ANALYSIS     │                                                 │
│ ──────────── │                                                 │
│ krztk2       │                                                 │
└──────────────┴─────────────────────────────────────────────────┘
```

- **Title bar**: `position: sticky; top: 0`, 2px bottom border, `bg-surface`.
  Left: 8px pixel logo sprite + `RETRACT` wordmark. Centre-left: the two nav
  links as `.px-tab`s. Right: three decorative `● ● ●` (`aria-hidden`, coloured
  `--danger`/`--warn`/`--ok`), theme toggle, `user.login`, and a labelled
  `LOG OUT` button. The dots are chrome, not controls — every function they
  might imply is also available as a labelled control beside them.
- **Sidebar**: 200px, `position: sticky; top: 28px`, own `overflow-y: auto`,
  2px right border, `bg-surface`. Nav items are 28px `.px-btn` blocks with a 2px
  `--accent` left rule when active. Bottom: the user card.
- **Below `lg`**: the sidebar collapses to a horizontal `.px-tab` strip directly
  under the title bar. No hamburger, no drawer.
- **Scroll**: the document scrolls. The sidebar scrolls independently. **No
  nested content scroll region is added.** `AnalysisDetailPage`, `FindingsTable`
  and `AgentChat` keep their existing `overflow-x-auto` / transcript scroller as
  they are today. Nesting a third scroll level behind a sticky title bar and a
  sticky sidebar is a mobile bug factory.
- **Login page** stays outside this frame (it is its own centred window).

## 6. Screens

### 6.1 Login — full pixel-art hero

The centred 26rem card becomes a `.px-frame` titled `RETRACT.EXE`:

- a **16×16 grid-rendered logo sprite** in the title bar area, blinking on a
  two-frame `anim-blink` cycle
- a **dithered sky backdrop** behind the frame — `.px-dither` using `--surface-2`
  and `--canvas`, i.e. a 2px checkerboard, not a gradient
- an **animated health-bar meter** (`.px-meter`, 20 cells) that fills left to
  right on `steps(20)`, loops, and is labelled `SYSTEM HEALTH`
- a 2px `--line` ASCII rule between the email form and the GitHub button

The segmented sign-in / create-account control becomes two `.px-tab`s. The
GitHub mark becomes a `PixelIcon`. All copy, the `aria-label="Email sign-in"`
form, both placeholders, the `Dev login` button, and the six `AUTH_ERRORS` strings
are unchanged.

### 6.2 Dashboard

Analysis rows become `.px-card` rows: the score sits in a sunken `.px-well` on
the left at 28px Silkscreen, the repo name in Silkscreen 13px, and the metadata
row in Pixelify Sans 11px. `Re-analyze` becomes `.px-btn--ghost`. Empty state uses
the new `EmptyState` component with a pixel sprite.

### 6.3 Repositories

Same row treatment as Dashboard. The URL input becomes `.px-input` with the
`default_branch` in JetBrains Mono inside a `.px-well`.

### 6.4 Analysis detail

- **Header**: `.px-panel` with a `← BACK` `.px-tab`, repo name in Silkscreen 20px,
  `StatusPill` as a `.px-badge`, and the four stats as `.px-well` tiles.
- **Tabs**: four `.px-tab`s with a 2px `--accent` underline. The sliding pill
  indicator is deleted.
- **Overview**: `ScoreHero` (ring + 6 meters) → `ApprovalQueue` → `ProgressFeed`
  → `FindingsTable` → `TrustPanel` → `HistoryCompare` → fix-plan summary card.
  Unchanged order.
- **`ProgressFeed`**: stays JetBrains Mono, but each row is a `.px-well` block
  with a 8px square status dot — no circles anywhere in the app.
- **`FindingsTable`**: 2px grid lines instead of hairlines; alternating rows get
  `.px-stripes`; severity badges use the ramp from §2.2; the `filter` and
  `severity` selects become `.px-input` with a `PixelIcon` chevron.
- **`ExploreTab`**: symbol kind badges become `.px-badge--flat`; the symbol list
  rows are `.px-well` blocks.

### 6.5 Agent chat

- Header gains a 2px `--line` bottom border; `New chat` is `.px-btn--ghost`.
- The tool chips become `.px-badge--flat` in JetBrains Mono 9px.
- Transcript messages: assistant text stays plain Pixelify Sans; user messages
  become `.px-well` blocks with a 2px `--accent` left rule instead of a soft
  accent bubble.
- Approval strips stay `--warn` tinted, but the approve button's hardcoded
  `#1a1205` is replaced by `--accent-ink`.
- Composer: `.px-input` + `.px-btn--primary`, label tri-state unchanged.

## 7. Code structure

### New files

| file | responsibility |
| --- | --- |
| `src/lib/palette.ts` | single source for `PILLAR_LABELS`, `SEVERITY_STYLES`, `STATUS_STYLES`, score thresholds, and per-theme colour resolution |
| `src/components/PixelIcon.tsx` | grid-string → crispEdges SVG |
| `src/components/Meter.tsx` | `Meter` (20 cells) and `ScoreRing` (20 radial cells) |
| `src/components/EmptyState.tsx` | the 9 inline empty/error/loading literals |
| `src/components/Loading.tsx` | dithered skeleton + `LOADING…` label |

### Rewritten

- `src/index.css` — full rewrite: `@theme`, `:root`, `.dark`, `@layer base`,
  `@layer components`. Still Tailwind v4 CSS-first, still `@theme inline` so
  all 21 color utilities keep working, still zero `tailwind.config.js`.
- `src/components/Layout.tsx` — window chrome + sidebar.
- `src/components/ThemeToggle.tsx` — two `PixelIcon`s, blocky active state.
- `index.html` — the three Google Fonts, a pixel `PixelIcon` data-URI favicon,
  and `theme-color` corrected per theme.

### Dedup that happens as a side effect

- `PILLAR_LABELS` is currently defined **4×** (`ScoreHero`, `FindingsTable`,
  `RemediationPlan`, `HistoryCompare`) → 1, in `palette.ts`.
- `SEVERITY_STYLES` is defined **3×** (`FindingsTable`, `ApprovalQueue`,
  `RemediationPlan`) → 1, in `palette.ts`.
- Three divergent score-threshold tables → 1.

### Deliberately unchanged

`api/*`, `lib/theme.ts`, `lib/clipboard.ts`, `lib/buildFixPrompt.ts`, the eve
token exchange, react-query hooks, `ThemeProvider`.

### Build order

The redesign is large, so it lands in four passes. Each pass leaves the app
runnable and fully tested.

1. **Foundation** — `palette.ts`, `PixelIcon.tsx`, `Meter.tsx`, the rewritten
   `index.css` tokens, `index.html` fonts and favicon. Nothing consumes these
   yet, so this pass is provably inert.
2. **Shell** — `Layout.tsx` window chrome + sidebar, `ThemeToggle`, and the
   background system. This is the change that is most visible and most
   reviewable in isolation.
3. **Primitives adoption** — every remaining page and component restyled; the
   9 inline empty/error/loading literals become `EmptyState`/`Loading`; the four
   `PILLAR_LABELS` copies and three `SEVERITY_STYLES` copies collapse into
   `palette.ts`; the three divergent score-threshold tables become one.
4. **New tests** — `palette.test.ts`, `Meter.test.ts`, `PixelIcon.test.ts`.

## 8. Accessibility

Pixel styling must not cost legibility. Non-negotiable:

- Body and all message text stays at **13px minimum**, Pixelify Sans.
- Focus is never removed. `:focus-visible` draws a 2px `--accent` inset ring on
  every interactive primitive. On `--accent` backgrounds the ring switches to
  `--ink` so it stays visible.
- `prefers-reduced-motion: reduce` neutralises `anim-step-in`, `anim-blink`, the
  score counter and every meter transition — existing block extended.
- Status is never colour-only. Every status carries a glyph and a word: the
  `● ● ●` window dots are decorative and carry no status; every real status has
  text.
- Contrast: all §2.1 pairs clear WCAG AA at their intended sizes. `--faint`
  (`#83769C`) is exempt — it is only ever used for disabled or tertiary text.
- Scanlines at 4% and the dot grid at 6% are below the threshold where they
  measurably reduce contrast.

## 9. Tests

No test in `src/test/` asserts on a class name. They query by **role, text,
placeholder, and `aria-label`** only, so a visual redesign cannot break them.
Verified across all 7 files.

Copy that must survive unchanged, because a test pins it:

| test | pinned strings |
| --- | --- |
| `AnalysisDetailPage` | back link, accessible name `/back/i`, `href="/"` |
| `AgentChat` | `"Ask about this analysis…"`, `"Send"`, `"Reconnecting…"`, `"Reconnecting to the agent…"`, `/Requested from the fix plan/` |
| `FindingsTable` | `"Fix with your agent"`, `"Copied ✓"`, `"fix with your agent"` |
| `LoginPage` | `"Sign in with GitHub"`, `"Dev login"`, `href="/api/auth/github/login"`, `form` / `"Email sign-in"`, `"you@example.com"`, `"Password"`, `"At least 8 characters"`, `"Sign in"`, `"Create account"`, the six `AUTH_ERRORS` strings |
| `RemediationPlan` | `"58"`, `"92"`, `"58 → 92"`, `/show the steps/`, `/show 1 findings/`, `"agent-authored"`, `"How to fix these issues"`, `"Download .md"`, `/on GitHub/`, `/Nothing to fix\. No open findings were recorded/`, `/Open fix plan/` |
| `VerifyEmailBanner` | `"Resend email"`, `"Email verified"`, `/Verification email sent/` |

Note `"Copied ✓"` pins a `✓`. The checkmark becomes a `PixelIcon` *beside* the
text; the text itself stays `"Copied ✓"`.

New tests to add:

- `palette.test.ts` — every severity/pillar/status has both a light and a dark
  colour; thresholds are monotonic.
- `Meter.test.ts` — 20 cells, dither at zero, `role="progressbar"` attributes.
- `PixelIcon.test.ts` — grid strings are rectangular and all-binary.

## 10. Risks

| risk | mitigation |
| --- | --- |
| Silkscreen at 9px is genuinely small | it is only ever used for badges, labels and numbers, never prose; browser zoom and OS scaling still apply |
| Pure black canvas + hard shadows is harsh | this is the aesthetic, chosen knowingly; `--surface` panels provide the visual rest |
| PICO-8 light mode is cramped for 6 pillars + 5 severities | §2.2/§2.3 assign every hue explicitly; `palette.test.ts` fails if a slot is unassigned |
| Dropping `backdrop-filter` changes the sense of depth | replaced by fill + bevel + hard shadow, which is depth in this language |
| Three hand-rolled bar implementations get replaced at once | `Meter.tsx` lands first and each call site migrates independently |