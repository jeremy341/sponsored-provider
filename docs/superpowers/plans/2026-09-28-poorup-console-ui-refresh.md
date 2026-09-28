> **Withdrawn (2026-09-28):** superseded by `docs/superpowers/plans/2026-09-28-ai-hackclub-theme-redesign.md`. Do not execute.

# Poorup-Style Provider Console UI Refresh Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:subagent-driven-development` (recommended) or `superpowers:executing-plans` to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Restyle every Provider Console surface with Poorup's exact pixel-parlor color, spacing, radius, typography, and SVG grammar while preserving all current product behavior.

**Architecture:** Keep the React 19/Vite SPA, FastAPI shell, React Router routes, API contracts, Radix interaction primitives, and Recharts data visualizations. Add one shared token system and a small typed pixel-SVG icon layer, then apply it in route families. Restyle the legacy `/dashboard` static shell separately with the same exact tokens; do not change its routing or behavior.

**Tech Stack:** React 19, TypeScript, React Router 7, Radix UI, Recharts, CSS custom properties, Vitest/Testing Library, FastAPI static shell.

**Spec:** `.ulpi/design/DESIGN.md`, `.ulpi/design/poorup-console-refresh.md`, `.ulpi/design/poorup-console-direction.md`.

## Skills and implementation method

- `superpowers:brainstorming` and Impeccable established the scope/direction and keep code changes behind a separate approval.
- `frontend-design-ui-ux` owns the locked tokens, component/state spec, and handoff.
- `frontend-design-review` owns the final frictionless/craft/trust review; `mobile-responsiveness` owns touch, safe-area, and viewport checks.
- `superpowers:writing-plans` structured this task list; `superpowers:test-driven-development` is required during execution so visual/interaction regressions are written and observed failing before implementation.
- Keep the work code-led. The user-pinned Poorup style wins over any concept-seed assignment; build the pixel SVG system as small React components and keep existing Radix semantics.

## Global Constraints

- Use the exact palette, spacing (`2, 4, 8, 12, 16, 20, 24, 32, 40px`), radii (`2px`, `3px`), and border weights (`1px`, `2px`) in `DESIGN.md`.
- Pixelify Sans is display/UI/body; Silkscreen is limited to short micro labels/readouts; IBM Plex Mono remains for model IDs, values, timestamps, and code.
- Verify Pixelify/Silkscreen asset licenses and include their attribution before copying local font files; do not request fonts remotely.
- Use provider-specific SVG icons with `shape-rendering="crispEdges"`; do not import Poorup game branding/art or use a crosshair cursor.
- Keep the current role boundaries, auth/invite behavior, route paths, `/v1`, API schemas, security, budget calculations, and data meaning unchanged.
- Preserve “not reported” and estimated/reported distinctions; do not fabricate usage or convert unknown values to zero/free.
- No new component/UI library. Keep Radix behavior for dialogs/tabs/menus and the existing Recharts SVG and accessible data tables.
- Avoid page-level horizontal overflow; dense tables may scroll inside their own container. Keep touch actions at least 44×44px.
- Deployment is outside this UI plan and requires a separate explicit rollout request.

## Review Focus

1. Red action fill and blue status are not used as low-contrast small text; semantic text/icon pairs remain readable.
2. Provider-specific pixel icons remain recognizable at small sizes and keep accessible names without accidentally changing native controls.
3. The dense usage/provider tables and model catalog fit 390px via internal scrolling/stacking, not body overflow or hidden actions.
4. Pixel fonts do not make long IDs, price precision, error copy, or form validation harder to read.
5. The legacy `/dashboard` and React portal share visual identity without changing their separate routes or behavior.

---

## File Map

- Modify `frontend/src/ui/styles.css` — replace HCAI zinc/red tokens and rounded surfaces with locked Poorup tokens, shared rules, responsive styles, and state treatments.
- Create `frontend/src/assets/fonts/` only for license-verified local Pixelify Sans/Silkscreen files; preserve font license notices. IBM Plex remains from the existing Fontsource packages.
- Create `frontend/src/ui/icons/PixelIcon.tsx` and `frontend/src/ui/icons/pixelIconData.ts` — typed provider glyph set and crisp SVG grid rendering.
- Modify `frontend/src/ui/App.tsx`, `frontend/src/ui/AuthPage.tsx`, and UI files under `frontend/src/ui/developer/` and `frontend/src/ui/operator/` — replace icon glyphs and bind shared components to the system without changing request behavior.
- Modify `frontend/src/ui/*test.tsx` and add `frontend/src/ui/PixelIcon.test.tsx`, `frontend/src/ui/PoorupVisualSystem.test.ts` — visual-token, icon semantics, route, control, and state regressions.
- Modify `app/static/style.css` only — reskin legacy `/dashboard`; preserve `app/static/index.html`, `app/static/app.js`, `/dashboard`, and every API interaction unless a test shows an existing behavior change caused by styling.
- Do not modify `app/main.py`, `app/portal_api.py`, `app/portal_db.py`, schemas, or database migrations for this visual-only task.

## Tasks

### Task 1: Lock shared Poorup tokens and font delivery

**Files:**
- Modify: `frontend/src/ui/styles.css`
- Create: `frontend/src/assets/fonts/*` and required license/notice files, only after license verification
- Test: `frontend/src/ui/PoorupVisualSystem.test.ts`

**Interfaces:** CSS roles mirror `.ulpi/design/DESIGN.md`: `--canvas`, `--chrome`, `--surface`, `--surface-raised`, `--surface-deep`, gold/text steps, `--action`, `--action-hover`, `--action-pressed`, semantic status, border, shadow, and focus variables. Task 1 owns the root token block, local font faces, compatibility aliases, and base control defaults; existing page/component declarations migrate in their owning Tasks 3–6. Task 7 verifies no HCAI palette/radius/font remnants remain anywhere in the finished UI.

- [ ] **Step 1: Write failing token contract tests** — assert exact canvas/panel/action and separate button-hover `#0C1C1D` tokens; assert `h1,h2,h3`, `.page-header h1`, and `.section-heading h2`/`.section-block h2` use `--font-display`, `.button` and `.icon-button` use the 2px control radius at desktop/mobile, and all spacing values exist; assert primary/body font faces are local and no remote font URL is present.
- [ ] **Step 2: Run `cd frontend && npm test -- --run src/ui/PoorupVisualSystem.test.ts`** — verify failures name missing Poorup values rather than test setup errors.
- [ ] **Step 3: Resolve font license/source** — check Poorup's local font asset notices and source metadata. If a face cannot be copied with permitted terms, keep the documented local fallback and flag the substitution for review; never add runtime font requests.
- [ ] **Step 4: Replace the current global token block and base type/control rules** — exact colors/radii/spacing from `DESIGN.md`; map shared heading typography to `--font-display`, use `--surface-button-hover` for base secondary/icon button hover, and use `--radius-control` for shared button/icon geometry including mobile overrides. Preserve focus visibility, color-scheme, body scrolling behavior, and reduced-motion rules.
- [ ] **Step 5: Run the focused token test, `npm run lint`, and `npm run typecheck`** — expect all to pass without runtime-style imports or remote font dependencies.

### Task 2: Add the provider-specific crisp SVG icon system

**Files:**
- Create: `frontend/src/ui/icons/PixelIcon.tsx`
- Create: `frontend/src/ui/icons/pixelIconData.ts`
- Modify: `frontend/src/ui/styles.css` — `.pixel-icon-svg { shape-rendering: crispEdges; }` because the linter rejects SVG `shapeRendering` JSX property names
- Test: `frontend/src/ui/PixelIcon.test.tsx`
- Modify: `frontend/package.json` / lock only if `lucide-react` is unused after every icon migration

**Interfaces:** `PixelIcon` takes `name: PixelIconName`, optional `size: 16 | 20 | 24 | 32`, `className`, and accessible decorative/label behavior. Pixel data maps named symbols to rows/cells; fill uses `currentColor` or semantic CSS variables. Decorative use defaults to `aria-hidden="true"`; meaningful standalone use requires an accessible label.

- [ ] **Step 1: Write failing tests** — one test verifies the SVG viewBox/`shape-rendering="crispEdges"`; one verifies decorative icons are hidden from the accessibility tree; one verifies named/labelled icons are accessible and unknown glyph names fail safely.
- [ ] **Step 2: Run the focused icon test and confirm the expected missing component failure.**
- [ ] **Step 3: Implement the typed grid-to-SVG renderer and provider icon registry** — include shell navigation, search, copy, add/edit, provider/network, people, shield, usage, close, check, and disclosure glyphs. Do not reuse Poorup logos or game sprites.
- [ ] **Step 4: Run icon tests and lint/typecheck.**

### Task 3: Restyle the shared shell, auth, and interaction primitives

**Files:**
- Modify: `frontend/src/ui/App.tsx`, `frontend/src/ui/AuthPage.tsx`, `frontend/src/ui/styles.css`
- Modify: `frontend/src/ui/icons/pixelIconData.ts` for any missing shell/auth glyphs; keep the `PixelIcon` rendering contract unchanged
- Modify tests: `frontend/src/ui/PortalShell.test.tsx`, `frontend/src/ui/AuthPage.test.tsx`

**Interfaces:** Keep `PortalRole`, `developerNav`, `operatorNav`, all React Router paths, mobile menu state, auth session handling, and Radix dialog semantics. Navigation items use `icon: PixelIconName` and render `<PixelIcon name={item.icon} ... />`. Replace shell/AuthPage Lucide glyphs with the provider pixel registry; page-specific icons in the rest of `App.tsx` stay with Tasks 4–5. Extend the registry only with the missing shell/auth glyphs (brand, lock, eye/reveal, menu, logout, preview, and right arrow) and add tests for them; do not change navigation permissions or redirects.

- [ ] **Step 1: Add/adjust failing shell and auth assertions** — route labels/active states, role switch, sign-in/invite mode, validation/error states, mobile sheet open/close, Escape/focus restore; assert shell/auth icons render as `PixelIcon` with decorative/labelled semantics.
- [ ] **Step 2: Verify those assertions fail for missing Poorup icon/theme behavior.**
- [ ] **Step 3: Restyle top shell, page headings, links, buttons, icon buttons, inputs, native selects, tabs, disclosures, notices, and auth panel** — 1px/2px gold rules, 2px/3px corners, short stepped feedback; keep native selects and Radix keyboard behavior.
- [ ] **Step 4: Run `npm test -- --run src/ui/PortalShell.test.tsx src/ui/AuthPage.test.tsx`, `npm run lint`, and `npm run typecheck`.**

### Task 4: Restyle developer pages and their overlays

**Files:**
- Modify: `frontend/src/ui/App.tsx`, `frontend/src/ui/developer/AllowanceSummary.tsx`, `DeveloperActivityPage.tsx`, `ModelAccessPicker.tsx`, `ModelCatalogPage.tsx`, `ModelCodeExamples.tsx`, `ModelDetailPage.tsx`, `frontend/src/ui/styles.css`
- Tests: existing `DeveloperTask9.test.tsx`, `DeveloperKeyDialog.test.tsx`, `DeveloperHome.test.tsx`, `ModelCatalogPage.test.tsx`, `ModelDetailPage.test.tsx`, `UsageCharts.test.tsx`

**Interfaces:** Keep all `PortalApi` methods, model/key/usage contract types, copy contents, private activity scope, and price precision unchanged. `PixelIcon` replaces remaining Lucide glyphs. Money/data values continue to use exact existing formatters.

- [ ] **Step 1: Extend failing visual-contract tests** — ensure catalog, model detail, activity, quickstart, key editor, and invite dialogs receive shared semantic classes/icons without changing displayed data or action results.
- [ ] **Step 2: Run focused tests and verify new visual hooks/state selectors are the failing assertions.**
- [ ] **Step 3: Apply Poorup tokens to home/runway/stat strip, key ledger/create/edit, provider-grouped catalog/detail, activity ledger, quickstart/code tabs, and invite card/dialog.**
- [ ] **Step 4: Preserve/loading/empty/partial/error/unpriced/unavailable states and keyboard access; never style unknown cost as free or omit the table alternative for charts.**
- [ ] **Step 5: Run developer page tests, full frontend tests, lint, and typecheck.**

### Task 5: Restyle operator pages, catalog management, and safeguards

**Files:**
- Modify: `frontend/src/ui/App.tsx`, files under `frontend/src/ui/operator/providers/`, `people/`, `usage/`, `frontend/src/ui/operator/MoneyRunway.tsx`, and `frontend/src/ui/styles.css`
- Tests: existing `ProviderTask8.test.tsx` and `UsageCharts.test.tsx`; add focused component tests only where current coverage misses keyboard/state behavior.

**Interfaces:** Preserve provider connection secrecy, sync lifecycle, model approval/availability switches, route priority, price provenance, allowance scopes, block confirmations, and emergency-stop semantics. UI forms submit the same values to the same API methods.

- [ ] **Step 1: Add failing assertions for provider disclosure, connection/price dialogs, allowance editor, usage filters, and guardrail destructive confirmations** — `aria-expanded`, disabled/loading state, accessible action name, and unchanged API payload.
- [ ] **Step 2: Verify focused failures are limited to the new shared interaction contract.**
- [ ] **Step 3: Restyle provider groups/offer tables/detail sheets/price review/route priority, people/invite/allowance rows, usage filters/charts/ledger, and safeguards/confirmations with the locked tokens.**
- [ ] **Step 4: Keep panels flat and table-first; put each disclosure inside its existing content hierarchy; use explicit words/icons with semantic colors.**
- [ ] **Step 5: Run operator/component tests, frontend suite, lint, and typecheck.**

### Task 6: Bring the legacy `/dashboard` shell into the same system

**Files:**
- Modify: `app/static/style.css`
- Test: existing Python tests covering `/dashboard` plus a focused static-route assertion if none verifies its local stylesheet/JS paths

**Interfaces:** Do not change `app/main.py`, static HTML structure, `app/static/app.js`, API endpoints, admin-token behavior, tab names, or action payloads. Keep `/dashboard` separate as a compatibility UI while making its tokens, borders, controls, tables, tabs, and modal match the portal.

- [ ] **Step 1: Add failing smoke/contract assertions that `/dashboard` still references only same-origin static assets and returns its existing HTML.**
- [ ] **Step 2: Confirm the assertions fail only for missing token/style consistency when appropriate.**
- [ ] **Step 3: Replace the legacy dashboard's zinc/red/rounded declarations with equivalent Poorup CSS variables and rectangular controls; retain its separate functional layout.**
- [ ] **Step 4: Run focused Python dashboard tests and `git diff --check`; verify `/dashboard`, `/static/style.css`, and `/static/app.js` still return their current success status.**

### Task 7: Responsive, accessibility, and full-regression finish

**Files:**
- Modify only files identified by the implementation/review tests above
- Verify: all UI route/component tests, `app/static` compatibility tests, and built frontend assets

- [ ] **Step 1: Capture developer/operator/auth/model-detail/provider/usage/guardrails and legacy dashboard at 1440×900, 1024×768, 768×1024, and 390×844 using real data only where available; use explicit empty/error states rather than fabricated production figures.**
- [ ] **Step 2: Fix any horizontal page overflow, clipped labels, sub-44px mobile actions, focus loss, or modal/sheet safe-area problems while keeping table overflow internal.**
- [ ] **Step 3: Run contrast checks for all text/state pairings, keyboard-only navigation, forced-colors/reduced-motion checks, and 200% zoom.**
- [ ] **Step 4: Run `npm test`, `npm run lint`, `npm run typecheck`, `npm run build`, the backend pytest suite, and `git diff --check`.**
- [ ] **Step 5: Run the Impeccable detector once on the final changed web UI targets and record remaining non-mechanical review notes.**
- [ ] **Step 6: Conduct a fresh frontend design review against the approved spec and the frictionless/craft/trustworthy pillars; stop after one batched fix/confirmation round.**
- [ ] **Step 7: Review the complete diff; do not commit, push, or deploy until separately requested.**

## Execution recommendation

Use subagent-driven implementation only after the user approves this written plan. The shell/token/icon foundation is sequential; after that, developer pages, operator pages, and the legacy static dashboard have mostly disjoint markup but share one CSS token file, so integrate them in ordered phases and review the stylesheet centrally. If subagents are selected, all must follow the workspace requirement to use GPT‑6 Luna at medium reasoning.
