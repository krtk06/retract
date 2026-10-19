---
name: Retract
description: "Repository health, computed not vibes — every screen is a numbered inspection dossier."
colors:
  canvas: "#faf9f7"
  surface: "#ffffff"
  surface-2: "#f4f2ee"
  line: "#e6e3dd"
  line-strong: "#cfcbc3"
  ink: "#1d1a16"
  muted: "#635d54"
  faint: "#6a655d"
  accent: "#1d1a16"
  accent-ink: "#faf9f7"
  ok: "#1f7a4d"
  warn: "#9a5b08"
  danger: "#b0392c"
  info: "#3568b8"
  hypo: "#6b59c1"
  sev-medium: "#7a6a2a"
  status-pending: "#6d6860"
  pillar-security: "#1d1a16"
  pillar-code-quality: "#3d3830"
  pillar-testing: "#5d564c"
  pillar-architecture: "#7d766a"
  pillar-documentation: "#9d9689"
  pillar-dependencies: "#beb7aa"
typography:
  display:
    fontFamily: "Source Serif 4, Georgia, Times New Roman, serif"
    fontSize: "3.75rem"
    fontWeight: 600
    lineHeight: 1
    letterSpacing: "-0.01em"
    fontFeature: "tnum"
  headline:
    fontFamily: "Source Serif 4, Georgia, Times New Roman, serif"
    fontSize: "3rem"
    fontWeight: 600
    lineHeight: 1.1
    letterSpacing: "-0.025em"
  title:
    fontFamily: "Source Serif 4, Georgia, Times New Roman, serif"
    fontSize: "1.125rem"
    fontWeight: 600
    lineHeight: 1.3
  body:
    fontFamily: "Geist, ui-sans-serif, system-ui, -apple-system, Segoe UI, sans-serif"
    fontSize: "0.8125rem"
    fontWeight: 400
    lineHeight: 1.5
  label:
    fontFamily: "Geist, ui-sans-serif, system-ui, -apple-system, Segoe UI, sans-serif"
    fontSize: "0.625rem"
    fontWeight: 500
    lineHeight: 1.4
    letterSpacing: "0.1em"
  evidence:
    fontFamily: "Geist Mono, ui-monospace, SFMono-Regular, Menlo, monospace"
    fontSize: "0.6875rem"
    fontWeight: 400
    lineHeight: 1.5
    fontFeature: "tnum"
rounded:
  sm: "2px"
  none: "0px"
spacing:
  "1": "4px"
  "2": "8px"
  "3": "12px"
  "4": "16px"
  "5": "20px"
  "6": "24px"
  "8": "32px"
components:
  button:
    backgroundColor: "{colors.surface}"
    textColor: "{colors.ink}"
    rounded: "{rounded.sm}"
    height: "32px"
    padding: "0 12px"
  button-primary:
    backgroundColor: "{colors.ink}"
    textColor: "{colors.canvas}"
    rounded: "{rounded.sm}"
    height: "32px"
    padding: "0 12px"
  button-primary-hover:
    backgroundColor: "color-mix(in srgb, var(--ink) 88%, var(--canvas))"
  button-danger:
    backgroundColor: "{colors.danger}"
    textColor: "#ffffff"
    rounded: "{rounded.sm}"
    height: "32px"
    padding: "0 12px"
  input:
    backgroundColor: "{colors.surface}"
    textColor: "{colors.ink}"
    rounded: "{rounded.sm}"
    height: "34px"
    padding: "0 10px"
  chip:
    backgroundColor: "{colors.surface}"
    textColor: "{colors.ink}"
    rounded: "{rounded.sm}"
    padding: "2px 8px"
  panel:
    backgroundColor: "{colors.surface}"
    rounded: "{rounded.sm}"
    padding: "24px"
  card:
    backgroundColor: "{colors.surface}"
    textColor: "{colors.ink}"
    rounded: "{rounded.sm}"
    padding: "14px"
  card-hover:
    backgroundColor: "{colors.surface-2}"
  stamp:
    backgroundColor: "transparent"
    rounded: "{rounded.sm}"
    padding: "2px 8px"
---

# Design System: Retract

## Overview

**Creative North Star: "The Verification Dossier"**

Every screen in Retract is a numbered inspection dossier: exhibits with verdicts and cited evidence. The interface refuses the dashboard-of-identical-cards default — the report is the interface, and reading it is the product. Scores arrive as stamped verdicts, pillars as a numbered schedule, findings as cited exhibits, and approvals as signatures on the record.

The material world is warm paper and ink. One monochrome ladder carries the light theme (paper under a desk lamp) and the dark theme (the same dossier at night, chalk ink on warm near-black); the two are co-equal. Structure is drawn with hairline rules, not shadows; display numerals are set in a screen serif with tabular figures; evidence — SHAs, `file:line`, tool names, counts — is set in Geist Mono so it reads as quoted from the machine. Hue is held in reserve and appears only where it is evidence: severity, run status, verification, hypotheses — and never without its word and its glyph.

The reading posture is calm density: quiet chrome, short declaratives, one accent's worth of expression. Primary actions are filled with ink itself, and every page sits on the same sheet: a fixed monochrome grain and a 4% ink vignette over the whole surface. Motion is one settling curve, and it carries feedback and continuity, not decoration — verdicts stamp once, indicators slide between destinations, rows answer the cursor, and the rest of the print stays still.

**Key Characteristics:**
- Warm paper-and-ink monochrome ladder; light and dark are co-equal, every token dual-valued.
- Hairlines and 2px corners; surfaces are flat — print does not float.
- Serif display numerals with tabular figures over a workhorse UI sans; Geist Mono for evidence.
- Numbered exhibits and stamp states; sequence carries information.
- Status is word + glyph + hue, never colour alone; hue is evidence only.
- Ink-filled primary actions; there is no second accent.
- One settling curve carries all motion; named moments land once and nothing loops for attention.
- A fixed monochrome grain and a 4% ink vignette sit on every page; texture never animates and never carries hue.
- Reduced motion is fewer and gentler, not none: travel, scale and layout stop; 140ms opacity and colour answers stay.

## Colors

The palette is a warm paper-and-ink monochrome ladder with five evidence hues held in reserve. Every token is dual-valued in `frontend/src/index.css` (`:root` and `.dark`); the hexes recorded here are the light definitions, and the dark pendants are co-equal — chalk ink on warm near-black, kept for AA legibility (exact dark values live in the stylesheet and in `.impeccable/design.json`).

### Primary
- **Dossier Ink** (#1d1a16): the text and the action. Body copy, headings, active-tab rules, focus rings, and the fill of every primary button — the accent is the ink itself, so there is no second accent.
- **Paper on Ink** (#faf9f7): the reversed plate — text on ink-filled controls, the selection block, the favicon.

### Secondary
- **Verified Green** (#1f7a4d): done runs, verified findings, passing coverage, positive score deltas.
- **Unverified Amber** (#9a5b08): running analyses, unverified states, at-risk scores, count-basis warnings.
- **Critical Red** (#b0392c): failed runs, critical severity, negative deltas, destructive actions.
- **Reference Blue** (#3568b8): low severity, tool activity in the transcript, history references.
- **Hypothesis Violet** (#6b59c1): agent hypotheses awaiting review — the not-yet-verified lane.
- **Medium Amber** (#7a6a2a): the one severity step with no other name — medium findings.

### Neutral
- **Warm Paper** (#faf9f7): the page canvas.
- **Report White** (#ffffff): panels, cards, inputs — paper laid on the desk.
- **Recessed Paper** (#f4f2ee): inset wells, hovered rows, active rail items, skeleton shimmer.
- **Hairline** (#e6e3dd): dividers, tick lattice, quiet rules.
- **Rule Ink** (#cfcbc3): control borders, stronger rules, scrollbar thumbs.
- **Second Ink** (#635d54): secondary text.
- **Margin Grey** (#6a655d): the label voice — field labels, metadata, evidence footers.
- **Pending Grey** (#6d6860): pending runs and informational severity.
- **Pillar ink ladder** (#1d1a16 → #3d3830 → #5d564c → #7d766a → #9d9689 → #beb7aa): security, code quality, testing, architecture, documentation, dependencies — one ladder, dark to light in that order. Each pillar token also carries its own dark pendant.

Severity and run status do not add colours: critical/danger, high/warn, medium (alone), low/info, and pending (the grey) are referenced by name through one table (`lib/palette.ts`), so a tone is always traceable to these primitives.

### Named Rules
**The One Accent Rule.** Primary actions are filled with ink itself; there is no second accent. Hue never appears as decoration.

**The Hue-Is-Evidence Rule.** Colour survives only where it is evidence — severity, run status, verification, hypotheses — and always arrives with its word and its glyph.

**The Ink Ladder Rule.** The six pillars share one ink ladder; sequence and label carry the difference. Never colour the pillars.

## Typography

**Display Font:** Source Serif 4 (with Georgia, Times New Roman, serif)
**Body Font:** Geist (with ui-sans-serif, system-ui, -apple-system, Segoe UI, sans-serif)
**Label/Mono Font:** Geist Mono (with ui-monospace, SFMono-Regular, Menlo, monospace)

**Character:** A screen serif carries the document's voice — every heading and every displayed numeral — while a workhorse sans carries the interface and Geist Mono carries evidence. The page reads as a typeset report, not a product UI.

### Hierarchy
- **Display** (600, 3.75rem/1, tabular figures, -0.01em): the stamped verdict score. The same serif treatment sets smaller report figures at 2.25rem (sample exhibit, score tiles) and 1.5rem (docket rows).
- **Headline** (600, 3rem/1.1, -0.025em): the login masthead — the one page that argues in display type.
- **Title** (600, 1.125rem): plate titles; the topbar wordmark runs 17px in the same voice.
- **Body** (400, 0.8125rem/1.5): UI prose and controls at 13px; the login argument runs 15px; dense ledger and sample lists at 12px.
- **Label** (500, 10px, 0.1em, uppercase): field labels and transcript attributions — it names a field or attributes a line.
- **Evidence** (Geist Mono, 400, 11px): SHAs, `file:line` citations, counts ledgers (`12v / 1h / 1d`), tool names, timestamps; exhibit footers run 10px.

### Named Rules
**The Figure Rule.** Every displayed numeral is set in the serif with tabular figures (`.figure`); figures are typeset, and units follow in faint sans (`/100`).

**The Evidence-Mono Rule.** Geist Mono is for evidence only — paths, SHAs, file:line, counts, tool names. Prose and controls stay in the workhorse sans; the serif never carries body text.

## Layout

The shell is a document frame: a 52px sticky topbar over a container capped at 1280px with 16px (24px at lg) gutters. At lg and up, a 232px rail sticks below the topbar at full remaining height, 4px item gaps, with a "Signed in" inset slab pinned at its foot; content sits beside it with a 32px gap. Below lg the rail becomes a horizontal tab strip pinned under the topbar — no hamburger, no drawer; navigation stays visible. The content column keeps the page's own scroll (deliberate: two data regions already scroll inside themselves), with 32–40px top padding and 96px at the foot; the footer is a hairline over a centered mono tagline, "repository health, computed not vibes".

The rhythm is a 4px grid: panel padding 20–24px, ledger-row padding 14px, controls 32px (inputs 34px), gaps 4–24px. Density is calm-dense: everything aligns to the same grid, and chrome stays quiet.

Browser chrome ships with the design: the favicon is the pulse mark reversed on ink, `theme-color` follows the active theme, and selection, caret, and thin scrollbar thumbs are ink-tinted.

### Named Rules
**The One Scroll Rule.** The content column keeps page scroll; only the rail and the two data regions (the findings table, the agent transcript) scroll inside themselves.

## Elevation & Depth

Flat at rest: this system uses tonal layering and hairlines, not shadows. Depth is the paper ladder — canvas, then laid paper (surface), then recess (surface-2) — plus 1px rules that separate rather than lift. The sheet itself carries texture: a fixed monochrome grain (SVG turbulence, 3% light / 5.5% dark) and a 4% ink radial vignette — static overlays that never animate and never carry hue. There is no blur, no glass, no translucency anywhere; paper is opaque. Shadows exist in exactly three places, and all are documented below.

### Shadow Vocabulary
- **Plate drop** (`box-shadow: 0 12px 40px var(--shadow)`; light `rgba(29, 26, 22, 0.08)`, dark `rgba(0, 0, 0, 0.4)`): the login plate alone — the one surface that lifts off the page at rest.
- **Stamp seal** (`box-shadow: inset 0 0 0 1px var(--surface), inset 0 0 0 2px currentColor`): the verdict stamp's inner rule, currentColor and tone-locked — a printed seal, not a drop shadow. The stamp's soft variant drops the inner rule for an 8% `currentColor` wash.
- **Row lift** (`box-shadow: 0 6px 18px var(--shadow)`): the hover shadow under an actionable row, paired with a 1px rise — repositories, analyses, and transcript suggestions only. Static exhibits, findings rows and plan steps never lift.

### Named Rules
**The Print-Does-Not-Float Rule.** Surfaces are flat; depth is paper tone, hairlines, and a static grain. The login plate is the only shadow at rest, and the row lift is the only shadow that answers a cursor.

**The Paper-Texture Rule.** The grain and the vignette are monochrome, fixed, and static — texture, not motion. They are never animated, never tinted, and never brightened into a glow.

## Shapes

Corners stop at 2px — panels, cards, buttons, inputs, chips, and stamps alike; enough to read as cut paper, never as pills. Tick-rule tracks and scrollbar thumbs are square (0). Structure is drawn with 1px hairlines: one weight for dividers and one for control borders, and a border is never thickened — if an edge needs more weight, the surface changes. The only doubled line in the system is the stamp's inner seal rule. Skeleton bars reuse the same 2px corner and the same paper tones.

### Named Rules
**The Hairline Rule.** Structure is drawn with 1px rules and paper tone; corners stop at 2px. Heavier edges are a different surface, not a thicker border.

## Components

The control language is printed: tickets, stamps, and ink fills on hairline plates. Nothing glows; everything is pressed — a 1px press, a 1px lift on rows that act, and one light sweep across filled controls, each a short beat on the one curve.

### Buttons
- **Shape:** gently squared (2px radius), 32px tall, `0 12px` padding, 13px/500 text, 6px icon gap.
- **Primary:** ink-filled (`var(--ink)`) with paper text; hover deepens the fill with a 12% canvas mix; active presses down 1px.
- **Hover / Focus:** 120ms colour/background transitions plus a 1px press on `:active`, all on the one curve; filled controls also carry the sheen — a single canvas-toned light band that sweeps across on hover (620ms), monochrome and hover-only. Focus is a 2px ink outline at 2px offset, and on ink-filled controls the ring flips to canvas so it never vanishes.
- **Variants:** danger (critical-red fill, white text, hover darkened 15%), solid (recessed paper), ghost (borderless; hover recesses), quiet (28px, muted text that inks on hover), icon (32×32 square); disabled drops to 45% opacity.

### Chips
- **Style:** print tickets, not pills — 11px/1.6, `2px 8px` padding, one hairline, 2px corners.
- **State:** tonal variants (e.g. hypothesis violet) use a 40% border and the 14% soft wash; the flat variant drops its border and left padding for inline captions.

### Cards / Containers
- **Corner Style:** 2px.
- **Background:** Report White; hovered rows move to Recessed Paper; inset wells begin recessed.
- **Shadow Strategy:** none at rest (see Elevation & Depth) — the login plate is the only surface that drops; actionable rows borrow the lift's hover shadow.
- **Border:** 1px hairline; hover strengthens it to Rule Ink.
- **Internal Padding:** 20–24px for dossier pages, 14px for ledger rows; inset wells pad 12–16px.

### Inputs / Fields
- **Style:** 34px tall, `0 10px` padding, Report White on one Rule Ink hairline, 2px corners, 13px text; placeholders in Margin Grey.
- **Focus:** no outline; the border goes ink and a 1px ink ring sits inside it — the field reads as ruled, not glowing.
- **Select / Textarea:** the same plate; the select hides the native arrow and insets a 9px chevron from the right; the textarea pads `8px 10px`.

### Navigation
Two faces of one index. The topbar is 52px and sticky, Report White over a Rule Ink hairline — drawn, not bordered: the rule is a 1px motion span that scales from 0 to 1 over 0.5s when the shell arrives, and renders full width instantly under reduced motion. The bar holds the serif wordmark at 17px on the left and the theme toggle, user login, and a ghost log-out on the right; the theme flip is one continuous colour inversion (320ms on the colour properties, applied for the switch only), and the toggle's glyph swaps with a short rotate-and-scale. The rail is the 232px section index at lg and up: 13px items with 2px corners, active items taking Recessed Paper plus a 1px ink rule on their left edge. Below lg the same items become the horizontal tab strip pinned under the topbar, active state a 2px ink underline. Rail, mobile strip and analysis-tab indicators all slide between destinations via layoutId (240–280ms), with the static rule as the no-motion fallback. A skip link rides above everything and lands top-left on focus.

### Verdict Stamp (signature)
The status seal: 10px/600 uppercase, 0.09em tracking, `2px 8px` padding, a currentColor border plus the inset seal rule — always glyph, word, and hue together (check · healthy · green; clock · unverified · amber; x · failed · red). The soft variant trades the inner rule for an 8% `currentColor` wash (the sample-exhibit tag). Running states add an announced "(live)" annotation, and in-flight marks elsewhere pulse as small ink or amber dots.

### Tick-Rule Meter (signature)
The one bar primitive — pillars, verification coverage, human acceptance. A 3px recessed track overlaid with a 10% repeating tick lattice; the fill carries the value's colour and settles left-to-right the first time it is seen (520ms on the one curve, staggered 60ms per pillar from a 200ms hold), with the serif figure counting up beside it (700ms) as one gesture. The value sits to the right in the serif figure. `null` means "not measured": a 45°-hatched Rule Ink track and an em dash — never zero, never a full bar — and the pillar row spells out "not measured" beneath the schedule.

### Score Hero (signature)
The one authored choreography in the app: the numeral counts up over 900ms, the verdict stamp lands (opacity/scale 1.12 → 1 over 240ms) as the count finishes, and the six pillar meters settle in sequence. The delta line carries direction with an arrow and ok/danger hue, the "No LOC measured" chip flags count-basis scores, and unmeasured pillars are explained under the schedule. The rest of the app's motion is feedback and continuity, not theatre.

### Evidence Furniture
One icon language: lucide's 24×24 grid at a 1.75px stroke, plus two drawn marks (the pulse logo, the GitHub mark); 10–24px, decorative by default, labelled when given a title. The sparkline is a 2px ink trend line with a 2.5px endpoint dot, drawn once (0.9s) with the head dot landing after; it renders only when the series has two or more points and is not flat, and it is `aria-hidden` decoration — the endpoint values beside it are the text equivalent, set in plain mono. Empty states are one inset frame (24px icon, 13px title, optional muted detail, an ink CTA route), and loading is a labelled status region over 36px-tall shimmer skeletons (1400ms linear).

### Motion System (signature)
- **One curve:** `cubic-bezier(0.16, 1, 0.3, 1)` — mass, not bounce — is the system's only easing: `EASE` in `lib/motion.ts`, identical to the CSS `--ease-out`. The engine loads lazily (LazyMotion, `domMax`) and `m` components render static-first, so content never waits on motion.
- **Named moments as shipped:** the verdict sequence (count-up, stamp land, meter settle on first view with a 200 + 60i ms pillar stagger); sliding indicators on the rail, the mobile strip and the analysis tabs; the theme flip as one continuous colour inversion; the login masthead's masked headline lines and staged sample exhibit (delays 0 / 0.09 / 0.24 / 0.32 / 0.5 / 0.6s); section reveals (0.42s, 8px rise, once) and row staggers capped by `stagger()` (step 35–50ms, cap 0.24–0.34s); the streaming caret after the last transcript line while an answer arrives; expanding surfaces (approval form, finding snippets, plan steps) that animate their height open; and the copy confirmation pop.
- **Feedback vocabulary:** the sheen on filled controls, the 1px press, the 1px row lift, the toggle's glyph swap — all short, all hover- or action-triggered. Nothing signals by looping except live states.
- **Reduced motion:** `MotionConfig reducedMotion="user"` drops travel, scale and layout everywhere at once; CSS caps every duration at 140ms and one iteration, stops the loops (pulse, float, caret, skeleton, the sheen sweep), swaps the entrance to an opacity-only fade, removes the lift's rise, and the sparkline renders finished at duration 0.

**The One-Curve Rule.** Every transition, entrance and count uses `cubic-bezier(0.16, 1, 0.3, 1)`. There is no second curve, nothing bounces, and nothing loops for attention.

**The Fewer-And-Gentler Rule.** Under `prefers-reduced-motion` the system drops travel, scale and layout — never feedback: entrances keep their fade, answers cap at 140ms, loops stop, and the sparkline arrives finished.

**The Lift-Is-Actionable Rule.** The 1px lift belongs to rows that do something — repositories, analyses, transcript suggestions. Static exhibits, findings rows and plan steps never lift.

## Do's and Don'ts

### Do:
- **Do** set every displayed numeral in the serif figure style with tabular figures, and follow it with its unit in faint sans.
- **Do** carry status as word + glyph + hue together; the word is the source of truth.
- **Do** fill primary actions with ink and keep hue out of the action layer.
- **Do** draw structure with 1px hairlines and paper-tone recesses; corners stop at 2px.
- **Do** render unmeasured as the hatched track and the em dash — "not measured" is not zero.
- **Do** define every colour token in both themes and route the theme through the `.dark` class; a stored explicit choice wins over the system preference, which owns first paint.
- **Do** move with the one curve (`cubic-bezier(0.16, 1, 0.3, 1)`) and let values land once; under `prefers-reduced-motion` travel, scale and layout stop while a 140ms opacity/colour answer stays.
- **Do** lift only rows that act — repositories, analyses, transcript suggestions — and leave static exhibits and findings rows still.
- **Do** keep the grain and vignette fixed, monochrome and static; texture is the world, not an animation.
- **Do** keep the sheen hover-only and monochrome — light across ink, never colour.

### Don't:
- **Don't** add shadows beyond the login plate's soft drop, the stamp's inset seal rule, and the row lift's hover shadow.
- **Don't** use blur, glass, or translucency; paper is opaque.
- **Don't** colour a severity or status without its word and its glyph.
- **Don't** introduce hue as decoration — hue is evidence only.
- **Don't** round past 2px or reach for pill shapes; tickets are print tickets.
- **Don't** put prose in Geist Mono or body text in the serif; each face has one job.
- **Don't** animate or tint the grain and vignette; texture is static paper, not a light effect.
- **Don't** run loops for attention; repeating motion is reserved for live states (in-flight dots, the streaming caret, loading shimmer) and stops under reduced motion.
