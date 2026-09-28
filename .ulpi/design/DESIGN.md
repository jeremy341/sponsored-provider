---
project: Sponsored Provider
register: product
aesthetic_direction: near-black developer console with a restrained pixel identity
color_strategy: monochromatic dark + one lime accent
design_system: Radix UI + existing React/Vite components themed with these tokens
design_variance: 3
motion_intensity: 1
visual_density: 7
---

# Design Read

A near-black operations console for sponsored AI access with a restrained retro-computing identity: fixed left rail, slim command bar, hairline-ruled dense data, and one vivid lime accent used on roughly 5% of any screen. The pixel layer — Silkscreen display labels, VT323 numerals, square status pixels, hard offset shadows on primary actions — gives the console an indie-game personality without costing scanability or trust. Money, keys, and model IDs always render in clean mono type.

This supersedes the earlier Ayu-dark amber direction (2026-09-28) and the zinc/red and Poorup drafts archived in this directory and `docs/superpowers/`.

## Signature

Allowance and budget runways are hard-edged dithered gauges with explicit numeric labels; hero stat values are VT323 phosphor-green digits; page titles, table headers, eyebrows, and status chips are uppercase Silkscreen micro-labels; primary buttons are lime with dark text and a 3px hard offset shadow that compresses 2px on press. The same grammar represents a developer's personal allowance and the operator's shared upstream exposure, but their labels and scopes never collapse into one another.

## Inspiration

- **Pixel consoles (Pixie-style landing pages):** take the almost-black field, warm off-white text, single vivid accent, chunky pixel display face contrasted with clean supporting type, sparse pixel-star decoration, and crisp hard-edged controls. Reject any logo, character artwork, illustration style, or layout from a specific product.
- **Developer infrastructure consoles:** take dense tables, hairline rules, mono discipline for identifiers and money, restrained status colors, and an instrumentation-not-marketing feel for charts.
- **Authority:** this file. Component contracts in `docs/superpowers/plans/` are historical; where they conflict with this file, this file wins.

## Color (locked)

| Role | Value | Use |
|---|---|---|
| Background | `#07100c` | App background |
| Deep background | `#050b08` | Inputs, code blocks, tracks, insets |
| Surface | `#0a1410` | Panels, table hover fills, quick-link tiles |
| Raised surface | `#0d1813` | Dialogs, sheets, secondary-button fills, hover |
| Foreground | `#eee9dc` | Primary text — warm off-white, never pure white |
| Muted foreground | `#9aa39c` | Secondary text, descriptions |
| Quiet foreground | `#77837a` | Micro-labels, disabled text, captions (AA on bg and surface) |
| Border | `#1d2b23` | Hairline dividers, section rules |
| Border strong | `#33443a` | Input/select/button outlines, table header rules |
| Primary lime | `#9bec5b` | CTAs, active nav, links, OK status, focus ring |
| Lime hover | `#b2f276` | Hover fill on lime controls |
| Lime soft | `rgb(155 236 91 / .10)` | Active nav wash, selected chips, success notice wash |
| Lime ink | `#07100c` | Text on lime fills |
| Destructive | `#f35b5b` / text `#ff7b7b` | Errors, global stop, destructive confirmations |
| Warning | `#e6c75f` | Pending/degraded states, price-required notices |
| Info | `#62b7ff` | Unknown/neutral markers |
| Chart series | `#9bec5b #62b7ff #e6c75f #5fd4c0 #c9a2ff` | Fixed rotation, no generated hues |

Contrast checks (on `#07100c` unless noted): foreground ≈15.9:1; muted ≈6.9:1; quiet ≈4.8:1 (micro-label sizes); lime ≈13:1; `#07100c` on lime ≈13:1; destructive ≈5.8:1; warning ≈9:1; info ≈7:1. Every status color ships with an explicit text label; color is never the only signal.

Distribution rule: ~80% near-black surfaces, ~15% cream/gray text, ≤5% lime. If a screen reads green, it is wrong.

## Type (locked)

| Role | Family | Use |
|---|---|---|
| Display (`--font-label`) | Silkscreen 700/400 | Page titles, login title, brand wordmark, table headers, eyebrows, status chips, primary-button labels, empty-state titles — **uppercase, 8–20px, never body copy** |
| Body / UI (`--font-body`) | Noto Sans Variable | Paragraphs, descriptions, nav, controls, table cells, dialogs — the default everywhere |
| Display numerals (`--font-display`) | VT323 | Stat values, allowance/runway amounts, allowance pill, price cards — **≥19px only** |
| Technical (`--font-mono`) | Maple Mono (fallback IBM Plex Mono) | Model IDs, key prefixes, request IDs, base URLs, timestamps, dense numeric cells, code |

All faces self-hosted via Fontsource (CSP-safe, OFL). Use tabular numerals for money, token totals, time, and IDs. Never set table cells, body copy, inputs, errors, long button labels other than primary CTAs, tooltips, or anything below 8px in a pixel face.

## Scales (locked)

- Spacing: 4px grid — 4 / 8 / 12 / 16 / 24 / 32 / 48. Content column max 1088px.
- Radius: `sm 2px / md 4px / lg 6px`. No pills on buttons; square corners on badges, tracks, and chips.
- Border: `1px` everywhere. Empty states use `1px dashed` strong border.
- Shadows: primary/destructive buttons and stop control `3px 3px 0 rgb(2 8 5 / .9)` (no blur), compressing to `1px 1px` with a 2px translate on `:active`; dialog `0 24px 64px rgb(0 0 0 / .6)`; cards and inputs carry no shadow.
- Motion: color/transform-only `120ms`; shell/dialogs `150ms`; no lift-scale, glow, gradients, or `steps()` animation; one `prefers-reduced-motion` block neutralizes all of it.
- Focus: `2px` lime outline, `2px` offset, no double ring. Lime-filled controls take the same outline — offset keeps it visible.
- Responsive checkpoints: `1440px`, `1024px`, `900px`, `767px`, `480px`, `390px`; 44px minimum touch targets ≤767px; no page-level horizontal overflow; tables scroll internally.

## Pixel layer rules (locked)

Allowed: pixel display font; 2–4px square decorative marks (brand mark, empty-state corner pixel, pixel stars on auth); square status dots; hard offset shadows on primary and destructive actions; hard-edged dithered runway fills (`repeating-linear-gradient(90deg, var(--lime) 0 6px, rgb(155 236 91/.45) 6px 8px)`); stepped step-list markers.

Rejected: CRT scanlines or vignettes, flicker/glitch/chromatic aberration, neon glow, glassmorphism or blur panels, gradients outside the runway dither, Minecraft-style notched borders, giant pixel illustrations, `image-rendering` tricks on text, `-webkit-font-smoothing: none`, and any pixel face in body copy, tables, inputs, or tooltips.

## Buttons

- **Primary:** lime fill, `#07100c` Silkscreen uppercase label, 1px lime border, 3px offset shadow. Used once per view for the main action (Create key, Invite person, Save policy).
- **Secondary:** raised-surface fill, strong border, off-white body font. Hover: border tints lime.
- **Quiet:** borderless text button; hover gains surface + border. For row actions.
- **Destructive:** solid red, dark text, same offset-shadow grammar — only in confirmations and the guardrail stop. Normal/healthy states never use red.

## Layout rules

- Left rail 15.5rem (collapsible to a 3.5rem icon rail, persisted), sticky; wordmark is a 15px lime pixel mark plus Silkscreen "sponsored_provider"; a Silkscreen micro-label names the portal (Developer console / Operator console); active nav is lime text on lime-soft with a 2px inset left bar.
- Command bar 52px: collapse trigger, Silkscreen page identity, allowance pill (square pixel status dot + VT323 numerals + Silkscreen period) right-aligned.
- Mobile ≤767px: rail becomes the Radix bottom sheet; tables scroll internally; no page-level horizontal overflow.
- Role nav (≤5 destinations each). Developer: Home · API keys · Models · Activity · Quickstart. Operator: Overview · People & keys · Providers & models · Usage · Guardrails & audit.
- Sections are flat: heading, optional description, thin top rule, content — not nested cards. Bordered panels are reserved for model cards, stat strips, code blocks, and dialog content.
- Stat strips are hairline `1px`-divided grids; VT323 values; the first cell's value is lime.
- Tables: muted Silkscreen headers, thin horizontal separators, mono for identifiers/money, internal horizontal scroll with `role="region"` + `tabIndex={0}`; the operator usage table keeps its 1060px minimum width scoped rule.
- Guardrails order: Global gateway (status + budget + stop) → Blocked sources → Audit log. The stop control is red; healthy state is normal text with a lime status pixel.
- Auth: almost-empty black field with sparse CSS pixel stars, centered panel, Silkscreen heading, lime CTA. No character artwork.
- Recharts stays semantic SVG; lime primary series, fixed 5-color rotation, `--line` grid, dark raised tooltip, no rainbow.

## Voice and product boundaries

Direct, calm, operational. Preserve Provider Console terminology and factual copy. Keep operator/developer ownership explicit; never imply upstream-reported cost when estimated, and never show unknown cost as zero/free — "Not reported" is the only honest absence. Keep usernames/passwords, invitations, per-user data, upstream secrets, model policies, request history, `/v1`, and server/API behavior unchanged. Empty states describe the real trigger and offer one next action; sample data is never fabricated.

## Consistency rule

Every screen must read as the same product if placed side by side.
