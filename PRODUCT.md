# Product

<!-- impeccable:product-schema 1 -->

## Platform

web

## Users

Developers and engineering leads deciding whether to depend on, merge into, or
inherit from a GitHub repository. They use Retract at a desk, in a browser,
alongside their IDE and terminal. The job: point Retract at a repository, get a
health score with verified, cited findings, and fix what matters with the eve
agent.

## Product Purpose

Retract scores repository health across six pillars (security, code quality,
testing, architecture, documentation, dependencies) using deterministic
analyzers and a repo symbol graph — not an LLM's opinion. Every finding is cited
to file:line, carries a severity, and is verified before it is shown. The eve
agent answers questions about one analysis and proposes fixes; consequential
agent actions (starting analyses, recording reviews) require human approval in
the UI. Success: a user trusts the score enough to act on it.

## Positioning

Computed, not vibes. Findings come from deterministic analyzers run over a
cloned repo and its symbol graph, each one cited and verifiable in one click.
A neighbouring product could copy the score UI but not the verification trail:
approval gates, human-review records, and the trust panel that shows what was
measured versus not measured.

## Operating Context

The browser app talks to a local API over SSE for live analysis progress. The
eve agent panel opens a session scoped to one analysis. Repositories are cloned
to the deployment's data directory; nothing is pushed back. Dev login exists for
local development only; production uses GitHub OAuth and email verification.

## Capabilities and Constraints

- Recent analyses dashboard, repository management, analysis workspace
  (Overview, Explore, Fixes, Agent tabs), remediation plan export, history
  comparison, trust panel.
- Live SSE progress feed while an analysis runs.
- Presentational redesign only: no new routes, API calls, or data.
- User-visible strings pinned by tests must survive verbatim.
- The eve client contract, SSE handling, react-query hooks and auth are
  untouched by design work.

## Brand Commitments

- Name: **Retract**. Wordmark lowercase in UI ("Retract"); no logo asset beyond
  the existing mark.
- Voice: precise, forensic, quiet. Short declaratives. No hype, no exclamation
  marks.
- Tagline in the footer: "repository health, computed not vibes".
- Visual register (user-bound): the verification dossier — audit-report print.
  Craft bar: Stripe, Linear, The Economist report print.

## Evidence on Hand

- A live local deployment with real analyses (13 repos; analysis #41 done with
  191 findings and a score) for verification screenshots.
- README and two approved design specs under `docs/superpowers/specs/`.

## Product Principles

1. Verification over assertion — status is never colour-only; every claim
   carries a word and a glyph.
2. Computed, not vibes — the interface reads as an instrument, not a toy.
3. Calm density — data-forward, quiet chrome, one accent's worth of expression.
4. The human approves — agent power is always gated behind visible consent.

## Accessibility & Inclusion

WCAG AA: body and placeholder text ≥4.5:1, large text ≥3:1. Status is never
colour alone. Keyboard focus is always visible. `prefers-reduced-motion` means
fewer, gentler animations: travel, scale and layout choreography stop; short
opacity and colour feedback (a 140ms answer) stays legible.

## Theme Default

First paint follows the system preference (`prefers-color-scheme`); the user's
explicit choice persists and wins afterwards. Dark and light are co-equal —
every token carries both values.
