> **Superseded (2026-09-28):** the Poorup pixel-console direction is replaced by the Ayu-dark console direction in `.ulpi/design/DESIGN.md` (`docs/superpowers/plans/2026-09-28-ai-hackclub-theme-redesign.md`). The implemented Poorup pass remains in git history; the uncommitted draft is archived at `docs/superpowers/archive/poorup-console-design-draft.md`. Do not implement this spec.

# Poorup-Style Provider Console · Design Specification

Status: superseded — see banner above. Original status line preserved below. This spec applies to the current Provider Console UI without changing server behavior.

## Job and audience

- **Developer:** quickly understand personal credit, keys, model access, request history, and how to make a first OpenAI-compatible request.
- **Operator:** inspect shared exposure, manage people/upstreams/models/prices, and reach blocks or emergency controls quickly.
- **Visitor:** accept an invite or sign in using existing local username/password behavior.
- **Success:** the next safe action and the scope of every usage/limit figure remain obvious while every visible route feels like one Poorup-derived product.

## Visual authority and synthesis

- Source: Poorup's current rendered `public/styles.css`, `public/clientSprites.js`, local font assets, and `.ulpi/design/DESIGN.md`; the GitHub repository documents the pixel-parlor stylesheet and bundled SVG/font assets: https://github.com/jeremy341/Poorup.
- Copy its color roles, compact geometry, spacing, type character, ruled panels, restrained inset shadow, and pixel-grid SVG construction.
- Do not copy Poorup's game logo, board/property art, mascots, gameplay language, or crosshair cursor. Build a provider-specific SVG icon family in the same low-resolution grammar.
- Preserve this product's name, role labels, APIs, route map, ownership boundaries, content facts, and existing interaction behavior.
- Keep the current React/Vite and Radix primitives; do not introduce a design system dependency or replace interaction primitives with custom non-semantic controls.

### Direction decision

The user explicitly pinned the Poorup visual system, so that choice overrides the Impeccable concept-seed assignment. The seed key `e7832357` is retained as a process trace, not a competing art direction. The jackfield challenger reinforces the already-required rule that state must use a shape/icon/text cue as well as color; the transit-map challenger reinforces explicit provider → model → eligible-route hierarchy. Their palettes, lane/map layouts, and motion are not imported. The after-hours Poorup world remains the only visual system.

## Routes and page inventory

| Surface | Existing route(s) | Visual work |
|---|---|---|
| Sign-in / invite registration | `/auth/login` | Pixel-console auth frame, accessible fields, invite/error/success states |
| Developer home | `/developer` | Lifetime stat strip, personal allowance runway, quickstart, keys/invites, model-use summary |
| Developer keys | `/developer/keys` | Key ledger, policy/status rows, create/edit/revoke flows, one-time secret reveal |
| Model catalog | `/developer/models` | Provider-grouped offers, filters, verified input/output/cache prices, availability |
| Model details | `/developer/models/*` | Identity, exact public ID, price provenance, technical details, cURL/JS/Python tabs |
| Developer activity | `/developer/activity` | Request ledger, filters, input/output tokens, cost provenance, status, latency |
| Developer quickstart | `/developer/quickstart` | Endpoint, copyable OpenAI-compatible example, selected model |
| Operator overview | `/operator` | Shared runway/health, aggregate usage, recent activity, quick access to safeguards |
| People | `/operator/people` | People/invite register, allowance and RPM controls, account status/actions |
| Providers and models | `/operator/providers` | Connection list, initial sync, brand catalog, price review, offer/routes, provider cap |
| Operator usage | `/operator/usage` | Period totals/charts, model/provider/person breakdowns, request ledger, safe IP/model actions |
| Guardrails | `/operator/guardrails` | Global stop, hard limits, blocks, runbook/audit controls |
| Legacy control room | `/dashboard` | Apply the same visual tokens to `app/static` while preserving the route and existing behavior |
| Unknown/session states | `*`, session loading/error | Shared pixel-console recovery layout; retain current destinations and auth behavior |

## Shared component contract

All values bind to `.ulpi/design/DESIGN.md`; do not introduce per-page colors, corner radii, or shadow systems.

| Component family | Required variants and states |
|---|---|
| Header, brand mark, role nav, account row, mobile navigation | Operator/developer links; active/focus/hover; role context; mobile sheet open/close; sign-out; session/loading/recovery |
| Buttons and icon buttons | Primary red, dark/gold secondary, quiet, destructive; hover/pressed/focus/disabled/loading; text labels remain clear |
| Inputs and selectors | Text/password/number/search/native select/checkbox; idle/focus/invalid/disabled/saving; browser-native menu behavior styled with dark color-scheme |
| Ledger panels and section headings | Flat deep/panel/raised fills; 1px rules, 2px emphasis, inset highlight; no nested-card walls |
| Stat strip and runway | Lifetime vs selected period clearly labeled; personal vs global vs provider scope explicit; used/reserved/remaining/reset; unknown remains “Not reported” |
| Tables, filters, and pagination | Search/sort/filter/loading/empty/partial/error; semantic headers; row actions; phone horizontal swipe without page overflow |
| Catalog groups and disclosures | `aria-expanded`, open/closed, focus/hover/pressed; keyboard operable and clear counts |
| Dialogs, sheets, popovers, and confirms | Radix behavior retained; focus trap/restore, Escape, backdrop, validation, pending/success/error; full-height phone sheet when needed |
| Charts | Recharts SVG retained; Poorup palette, square plot grid, custom pixel markers, readable legend/tooltip and equivalent data table |
| Code blocks and copy controls | Same-origin `/v1` samples only; model ID and placeholder key; horizontal internal scroll; copy success/error; no secrets |
| Status, notices, empty/loading states | Pixel glyph plus text; never color alone; retry where valid; no invented metrics or “free” for unknown cost |

## SVG icon specification

- Add a typed React `PixelIcon` registry for navigation, key, model/catalog, activity, code, provider/network, people, shield, usage, search, add/edit/copy/block, confirm, and close/chevron actions.
- Use hand-authored pixel grids/rectangles in inline SVG with `shape-rendering="crispEdges"`; canonical viewBox is 8–16 cells and display sizes are 16/20/24/32px. Palette uses `currentColor`/design variables.
- Decorative icons are `aria-hidden`; icon-only actions retain visible accessible names. Do not put decorative SVGs in paragraphs or replace recognizable native affordances.
- Reuse no Poorup gameplay sprite or wordmark. Keep cursor behavior native.

## Anti-slop constraints

- No purple/blue glow, neon edge, gradients, glassmorphism, pill-button takeover, emoji iconography, or generic repeated three-card grids.
- No decorative board spaces, game wordmark, mascots, fake metrics, invented provider health, or stock “AI control room” visuals.
- Pixel detail belongs in typography, icons, rules, and selected affordances—not rasterized text, tiny paragraphs, or unreadable data.
- Dense data uses ledger rows, not nested cards. A kicker or numbered marker appears only when it communicates a real section or sequence.

## Motion and states

- Match Poorup's short stepped response: hover 80–120ms, press 60–80ms, panel 120–160ms. No bounce, perpetual blinks, or animation that delays content.
- Respect `prefers-reduced-motion`; focus and state changes must be understandable with motion disabled.
- Auth: idle, validation, submitting, accepted/rejected invite, expired session, server/network error.
- Data pages: loading, no data, known data, partial/unknown pricing, stale catalog, API error/retry, action pending/success/failure.
- Key/provider/block actions: preserve current confirmation and privilege requirements; no route or policy mutation is added by styling.

## Responsive and accessibility requirements

- Keep the existing role-aware top-navigation model. At 390px, use the compact header and accessible navigation sheet; stack dense controls and make dialogs/sheets fit safe areas.
- At 768px, wrap metric strips/toolbars without overlap and keep tables independently swipeable. At 1024–1440px, preserve the current content hierarchy while allowing provider/activity tables useful width.
- Page width must never exceed viewport width at 390/768/1024/1440. Important actions target at least 44×44px on touch layouts. Text, key policy, price, and error content may not be clipped to achieve pixel density.
- Verify WCAG AA text/UI contrast using the locked exact palette. Red/blue are not small body-text colors on panel; use readable ink and pair every semantic state with text/icon.
- Keyboard: skip link, logical tab order, visible gold focus, usable selects, dialogs, tabs/disclosures, Escape/restore focus, 200% zoom, screen-reader labels/announcements.

## Behavioral boundaries

- No backend, database, API payload, session, authorization, budget, routing, model approval, logging, or `/v1` behavior changes.
- Never expose upstream credentials, internal URLs, prompts/completions, another user's activity/IP, or hidden model data.
- Preserve exact distinction between reported, estimated, unpriced, and zero usage. Visual formatting must not change numerical calculations.
- Keep `/dashboard` endpoint and its current JavaScript behavior; only apply the same visual rules to its static assets.

## Acceptance and preflight

1. All listed routes, shared controls, overlays, and important states use the tokens in `DESIGN.md`; HCAI zinc/red, pill radii, and Lucide glyphs are absent from the finished portal.
2. Poorup colors/spacing/radii/type are applied consistently; no game branding/art is imported; every SVG is provider-specific and crisp at its intended size.
3. Existing React/Radix semantics and all API/data/role/security behavior remain intact.
4. Desktop/tablet/phone captures at 1440, 1024, 768, and 390px show no page overflow, clipped content, or unreachable action.
5. Tests cover icon semantics, shell/auth routes, key/model/provider flows, legacy dashboard asset path, chart table equivalence, and responsive interaction targets.
6. Final design review covers frictionless insight-to-action, craft/system consistency, trustworthy data/error states, contrast, keyboard, reduced motion, and mobile navigation.

Planning preflight: identity—one Poorup token/icon/type system; anti-slop—no generic rounded SaaS cards, gradients, glass, emoji, or fake stats; state/flow—loading, empty, partial, success, error and expiry included; accessibility—contrast/keyboard/focus/44px targets specified; layout—table, ledger, runway, catalog, and code surfaces use distinct compositions; cognitive load—role nav stays compact and each view has one primary action.

Spec-quality self-critique (not implementation approval): distinctiveness 4/4; hierarchy 3/4; token consistency 4/4; accessibility coverage 3/4; state coverage 4/4; copy/trust 4/4; restraint 3/4; motion motivation 3/4. **28/32.** Accessibility is 3 because exact Poorup blue/red tokens are not safe small text on dark surfaces; the spec assigns those hues only to large marks/fills and pairs states with readable ink and labels. Render quality remains unverified until the planned captures and review.

## Build handoff

Implement this spec exactly, binding all UI to `.ulpi/design/DESIGN.md`. Use the existing React/Vite + Radix primitives and a small internal pixel SVG component; do not add a UI framework or redesign route/API behavior. The backend/data contract remains untouched. Build in the phase order in `docs/superpowers/plans/2026-09-28-poorup-console-ui-refresh.md` and complete the test/visual gates before any deployment.

## Skills used for this plan

- `superpowers:brainstorming` — identify scope, confirm the Poorup visual direction, and keep implementation behind a separate approval.
- `impeccable` (`context`, `new-work`, `shape`, concept seed, and surface brief) — inspect the incumbent visual truth, record the user-pinned direction, and preserve a compact route contract. The seed cannot overrule the user's choice.
- `frontend-design-ui-ux` — define the locked design language, route/state matrix, component behavior, and handoff.
- `frontend-design-review` — final review lens: frictionless insight-to-action, craft/system consistency, and trustworthy data/error states.
- `mobile-responsiveness` — responsive breakpoints, safe areas, internal table scroll, and touch targets.
- `superpowers:writing-plans` — phased implementation plan with testable task boundaries.
- `superpowers:test-driven-development` — required for the later implementation tasks; each behavior/style contract begins with a failing regression test.

This design-only pass intentionally does not run the production-UI detector or claim visual QA; those are implementation/finish gates.
