---
project: Sponsored Provider
register: product
aesthetic_direction: Ayu-dark IDE console with a bitmap accent layer
color_strategy: restrained
design_system: Radix UI + existing React/Vite components themed with these tokens
design_variance: 4
motion_intensity: 1
visual_density: 7
---

# Design Read

A dark operations console for sponsored AI access, modeled on the ai.hackclub.com console shell: fixed left rail, 56px command bar, hairline-ruled dense data, one amber accent. A restrained bitmap layer — VT323 display numerals, Silkscreen micro-labels, stepped progress bars — gives it a phosphor-terminal character without costing scanability.

## Signature

Allowance and budget runways are stepped dithered gauges with explicit numeric labels; hero stat values are amber VT323 phosphor digits; table headers, eyebrows, and status chips are uppercase Silkscreen micro-labels. The same grammar represents a developer's personal allowance and the operator's shared upstream exposure, but their labels and scopes never collapse into one another.

## Inspiration

- **ai.hackclub.com console:** take the shell (16rem rail, 56px command bar, allowance pill), the Ayu-dark palette discipline, hairline stat grids, dense tables with amber OK, and mono/tabular numeral discipline. Reject its logo, name, copy, OAuth, `/proxy/v1` endpoint, and light theme.
- **Retro bitmap layer:** VT323 for display numerals ≥18px, Silkscreen for 11–12px uppercase labels, stepped runway fills. Reject scanlines, notched corners, icon restyling, CRT flicker, font-smoothing hacks, and any pixel face in body copy, tables, or inputs.
- **Authority:** this file. `docs/superpowers/plans/2026-09-28-ai-hackclub-theme-redesign.md` carries the full component contracts and task breakdown. The Poorup and zinc/red systems are superseded (see banners in their files; the uncommitted Poorup draft is archived at `docs/superpowers/archive/poorup-console-design-draft.md`, the implemented Poorup pass remains in git history).

## Color (locked)

| Role | Value | Use |
|---|---|---|
| Background | `#0b0e14` | App background |
| Card | `#0d1017` | Panels, tables, code blocks |
| Popover | `#0f131a` | Dialogs, sheets, menus |
| Sidebar | `#0f131a` / border `#11151c` | Left rail and its right edge |
| Secondary | `#131721` | Hover/active fills, chips, allowance pill |
| Secondary / muted fill | `#131721` | Hover/active fills, chips, muted boxes |
| Foreground | `#bfbdb6` | Primary text — warm gray, never pure white |
| Muted foreground | `#7d8595` | Secondary text (AA-corrected from the reference `#6c7380`) |
| Quiet foreground | `#7a818d` | ≥19px display type or disabled text only (AA-corrected; was `#6c7380`) |
| Primary amber | `#e6b450` | CTAs, active nav, links, OK status, focus ring |
| Primary foreground | `#0b0e14` | Text on amber fills |
| Primary soft | `rgb(230 180 80 / .10)` / border `.30` | Active nav wash, avatar wash |
| Destructive | `#d95757` / text `#f08a80` | Errors, disabled/rejected states, global stop |
| Success | `#aad94c` | "Available/approved" model chips only |
| Info | `#59c2ff` | Unknown/neutral markers |
| Border | `rgb(71 82 102 / .35)` | Dividers only |
| Border strong | `#5a6478` | Input/select/button outlines (≥3:1) |
| Chart series | `#e6b450 #59c2ff #aad94c #d2a6ff #f07178` | Fixed rotation, no generated hues |

Contrast checks: `#bfbdb6` on `#0b0e14` is ~10.3:1; `#7d8595` on card is ~5.1:1; `#e6b450` on card is ~10:1; `#d95757` on card is ~4.9:1. Pair every status color with an explicit text label or icon; amber carries both action and OK semantics, so green is reserved for available/approved chips only.

## Type (locked)

| Role | Family | Use |
|---|---|---|
| Body / UI (`--font-body`) | Noto Sans Variable | Paragraphs, descriptions, nav, controls, table cells, dialogs — the default everywhere |
| Display numerals (`--font-display`) | VT323 | Stat values, fact values, allowance/runway amounts, hero numbers — **≥18px only** |
| Micro-labels (`--font-label`) | Silkscreen | Table headers, eyebrows, status chips, section labels, badge/step numerals — **11–12px uppercase, `letter-spacing: .06em`** |
| Technical (`--font-mono`) | Maple Mono (fallback IBM Plex Mono) | Model IDs, key prefixes, request IDs, base URLs, timestamps, dense numeric cells, code |

All four faces self-hosted via Fontsource (CSP-safe, OFL). Use tabular numerals for money, token totals, time, and IDs. Never set table cells, body copy, inputs, errors, long button labels, tooltips, or anything below 11px in a pixel face. Verify Silkscreen 11px labels at ≥4.5:1 or promote their color.

## Scales (locked)

- Spacing: 4px grid. Content column `max-w-5xl (1024px)`, `px-4 py-8 sm:px-6 sm:py-10 lg:px-8`.
- Radius: `sm .27rem / md .36rem / lg .45rem (cards, tables, inputs) / xl .63rem`; `pill 999px` for the spend pill, chips, avatar only. No pill buttons.
- Border: `1px` everywhere. Empty states use 1px dashed.
- Shadows: cards/inputs `0 1px 2px rgb(0 0 0/.05)`; dialog `0 20px 52px rgb(0 0 0/.72)`; overlay `rgb(0 0 0/.72)`.
- Motion: color-only `150ms cubic-bezier(.4,0,.2,1)`; shell/dialogs `150ms cubic-bezier(.23,1,.32,1)`; no lift, scale, glow, or gradients; one `prefers-reduced-motion` block neutralizes all of it.
- Focus: `2px` amber outline, `2px` offset, plus `box-shadow: 0 0 0 4px rgb(230 180 80/.28)`; amber-filled controls use a `#bfbdb6` outline instead.
- Responsive checkpoints: `480px`, `767px`, `1024px`, `1440px`; 44px minimum touch targets at all widths.

## Retro layer rules (locked)

- Stepped runway/progress fills use a hard-edged dither (`repeating-linear-gradient(90deg, var(--primary) 0 6px, rgb(230 180 80/.55) 6px 8px)`) on a `--secondary` track with a 1px `--border-strong` rule; the numeric percentage/amount stays visible as text and the bar keeps `role="progressbar"`; over-cap fills switch to destructive.
- Pixel assets (if any) use `image-rendering: pixelated`; no other pixelation hacks.
- Explicitly rejected this round: CRT scanline/vignette overlays, notched `clip-path` corners, square-cap icon restyling, `steps()` animation, `-webkit-font-smoothing: none`. Re-adding any of these is a new design decision, not a polish step.

## Icon language

Lucide only, 16px, 1.5px stroke. The Poorup-era PixelIcon family is removed with the old system. Icons never stand alone for status — always paired with text.

## Layout rules

- Left rail 16rem (collapsible to a 3rem icon rail, persisted), 56px command bar with collapse trigger, page title/breadcrumb, and the allowance pill (`● $used / $cap PERIOD`, dot thresholds 60/90%).
- Mobile ≤767px: rail becomes the labeled Radix sheet; tables scroll internally; no page-level horizontal overflow.
- Role nav (≤5 destinations each). Developer: Home · API keys · Models · Activity · Quickstart. Operator: Overview · People · Providers · Usage · Guardrails. No `Resources → Documentation` entry until a docs site exists.
- Stat strips are hairline `gap-px` grids inside one bordered box; model cards 1/2/3 columns; Quickstart 1/2 columns.
- Recharts stays semantic SVG; axes/grid/tooltip themed from tokens; the spend donut cycles the fixed 5-color series.
- The legacy `/dashboard` Control Room is deleted, not restyled.

## Voice and product boundaries

Direct, calm, operational. Preserve Provider Console terminology and factual copy. Keep operator/developer ownership explicit; never imply upstream-reported cost when estimated, and never show unknown cost as zero/free. Keep usernames/passwords, invitations, per-user data, upstream secrets, model policies, request history, `/v1`, and server/API behavior unchanged.

## Consistency rule

Every screen must read as the same product if placed side by side.
