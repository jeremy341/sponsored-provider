# OpenRouter-Inspired Pixel UI Demo Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the current portal presentation with a dense 1920px-first dark/pixel dashboard while preserving existing API contracts, role separation, auth, and key-management behavior.

**Architecture:** Keep the existing React/Vite router and backend client intact. Build a small reusable dashboard component layer and a single role-aware shell, then restyle/recompose the existing developer and operator pages around current API data. Unsupported screenshot concepts stay disabled or explicitly unavailable rather than fabricating backend behavior.

**Tech Stack:** React 19, TypeScript, Vite, React Router, Radix UI, Lucide React, Recharts, Vitest, Testing Library.

**Spec:** `docs/superpowers/specs/2026-09-30-openrouter-pixel-ui-demo-design.md`

## Global Constraints

- Primary visual target: 1920×1080; usable down to 1280px desktop.
- Do not change backend contracts, auth, provider routing, billing semantics, or role protection.
- Real API data always wins; unsupported metrics render as `—`, disabled controls, or explicit empty states.
- Keep destructive key/operator actions behind existing confirmation semantics.
- Reuse existing fonts and dependencies; no new visual dependency is required.
- Visual tokens: near-black/navy surfaces, 1px blue-gray borders, violet primary accent, cyan/green semantic data/status accents, 4–6px radii.

## Review Focus

- Missing allowance data must not crash the shell or display fabricated money values.
- Developer routes must never expose operator-only navigation/actions and vice versa.
- Narrow desktop layouts must retain table usability through compression or horizontal scrolling rather than clipped controls.
- API-key reveal/edit/revoke/archive semantics must remain unchanged after layout changes.
- Empty/partial provider/model/activity data must render neutral empty states instead of fake analytics.

---

### Task 1: Establish the visual system and dashboard primitives

**Files:**
- Create: `frontend/src/ui/components/DashboardPrimitives.tsx`
- Create: `frontend/src/ui/components/DashboardPrimitives.test.tsx`
- Modify: `frontend/src/ui/styles.css`
- Modify: `frontend/src/main.tsx` only if font imports need consolidation.

**Interfaces:**
- Produces: `Panel`, `MetricCard`, `StatusBadge`, `ProgressBar`, `PageHeader`, `FilterBar`, `SegmentedTabs`, and `EmptyState` components with class-based styling hooks.
- Consumes: existing Lucide icons and current font packages.

- [ ] **Step 1: Write failing primitive tests**

Cover semantic status classes, progress clamping at 0–100, accessible headings/labels, and empty-state rendering.

- [ ] **Step 2: Run focused tests and verify failure**

Run: `cd frontend && npm test -- DashboardPrimitives.test.tsx`

Expected: FAIL because the new primitives do not exist.

- [ ] **Step 3: Implement the reusable primitives**

Create focused presentational components only; no API fetching inside them.

- [ ] **Step 4: Replace the stylesheet token layer**

Define semantic CSS custom properties for canvas/surface/border/text/violet/cyan/success/warning/error, compact typography, 4–6px radii, 36–40px controls, 44–52px dense rows, keyboard focus rings, and responsive breakpoints at 1600px and 1280px.

- [ ] **Step 5: Run tests and typecheck**

Run: `cd frontend && npm test -- DashboardPrimitives.test.tsx && npm run typecheck`

Expected: PASS.

- [ ] **Step 6: Commit**

Commit message: `feat: add dense dashboard visual system`

---

### Task 2: Rebuild the shared role-aware shell

**Files:**
- Modify: `frontend/src/ui/shell/AppShell.tsx`
- Modify: `frontend/src/ui/shell/Sidebar.tsx`
- Modify: `frontend/src/ui/shell/AllowancePill.tsx`
- Modify: `frontend/src/ui/shell/TopBar.tsx`
- Modify: `frontend/src/ui/shell/nav.ts`
- Modify: `frontend/src/ui/PortalShell.test.tsx`
- Modify: `frontend/src/ui/styles.css`

**Interfaces:**
- Consumes: current route/session role and existing allowance data.
- Produces: one fixed 272px desktop rail, active-link styling, bottom allowance mini-card, and responsive collapsed state shared by developer and operator routes.

- [ ] **Step 1: Extend shell tests**

Assert role-specific links, active navigation state, allowance present/empty behavior, and accessible collapse controls.

- [ ] **Step 2: Run focused shell tests and verify expected failures**

Run: `cd frontend && npm test -- PortalShell.test.tsx`

- [ ] **Step 3: Implement the new shell composition**

Keep route definitions and protection intact; change only structure/presentation needed for the screenshot-like rail and content frame.

- [ ] **Step 4: Add desktop-first shell CSS**

Target 272px sidebar, 28–32px content gutters, compact nav rows, violet selected state, and horizontal-safe behavior under 1280px.

- [ ] **Step 5: Run shell tests and typecheck**

Run: `cd frontend && npm test -- PortalShell.test.tsx && npm run typecheck`

Expected: PASS.

- [ ] **Step 6: Commit**

Commit message: `feat: redesign portal shell and navigation`

---

### Task 3: Compose the developer dashboard, usage, and API-key surfaces

**Files:**
- Modify: `frontend/src/ui/App.tsx`
- Modify: `frontend/src/ui/developer/AllowanceSummary.tsx`
- Modify: existing developer API-key components/dialogs referenced by `App.tsx`
- Modify: `frontend/src/ui/DashboardAnalyticsPanel.tsx`
- Modify: `frontend/src/ui/MonthlyAllowance.test.tsx`
- Modify: `frontend/src/ui/developer/DeveloperKeyDialog.test.tsx`
- Modify: `frontend/src/ui/styles.css`

**Interfaces:**
- Consumes: existing developer dashboard, allowance, activity, and key APIs.
- Produces: 1920px overview grid, allowance panel, dense usage analytics, key table, and right-side key create/edit presentation without changing key lifecycle behavior.

- [ ] **Step 1: Add failing tests for redesigned states**

Cover empty allowance values, key create drawer/dialog open-close behavior, existing reveal-once semantics, and neutral rendering when analytics fields are absent.

- [ ] **Step 2: Run focused developer tests**

Run: `cd frontend && npm test -- MonthlyAllowance.test.tsx DeveloperKeyDialog.test.tsx`

- [ ] **Step 3: Recompose developer overview and usage using primitives**

Use current data for four compact metric cards, allowance progress, usage chart/breakdowns, and recent requests. Omit or neutralize unsupported screenshot metrics.

- [ ] **Step 4: Recompose API-key management**

Use a dense table plus desktop side panel/dialog while calling the same existing create/edit/revoke/archive handlers.

- [ ] **Step 5: Run focused tests and typecheck**

Run: `cd frontend && npm test -- MonthlyAllowance.test.tsx DeveloperKeyDialog.test.tsx && npm run typecheck`

Expected: PASS.

- [ ] **Step 6: Commit**

Commit message: `feat: redesign developer dashboard usage and keys`

---

### Task 4: Redesign Models, Activity/Logs, and Quickstart/Playground

**Files:**
- Modify: `frontend/src/ui/developer/ModelCatalogPage.tsx`
- Modify: `frontend/src/ui/developer/ModelDetailPage.tsx`
- Modify: `frontend/src/ui/developer/DeveloperActivityPage.tsx`
- Modify: `frontend/src/ui/App.tsx`
- Modify: `frontend/src/ui/developer/ModelCatalogPage.test.tsx`
- Modify: `frontend/src/ui/developer/ModelDetailPage.test.tsx`
- Modify: `frontend/src/ui/developer/DeveloperTask9.test.tsx`
- Modify: `frontend/src/ui/styles.css`

**Interfaces:**
- Consumes: current model catalog/detail/activity data and current quickstart functionality.
- Produces: model filter toolbar, featured/summary cards, selectable compare panel using only catalog data, master-detail activity layout, and two-column quickstart workbench.

- [ ] **Step 1: Write/extend failing model and activity tests**

Cover compare selection max/state, empty catalog/activity rendering, provider-qualified model identity, and selected activity-row detail behavior where data exists.

- [ ] **Step 2: Run focused tests and verify failures**

Run: `cd frontend && npm test -- ModelCatalogPage.test.tsx ModelDetailPage.test.tsx DeveloperTask9.test.tsx`

- [ ] **Step 3: Implement dense Models composition**

Keep existing search/filter semantics; make comparison presentation frontend-only and derived solely from existing model fields.

- [ ] **Step 4: Implement Activity/Logs master-detail composition**

Show only existing request metadata; unsupported request/response tabs must not fabricate content.

- [ ] **Step 5: Recompose Quickstart/Playground**

Keep real existing request/example behavior. Any screenshot control without a backend capability is visibly disabled/demonstrative.

- [ ] **Step 6: Run focused tests and typecheck**

Run: `cd frontend && npm test -- ModelCatalogPage.test.tsx ModelDetailPage.test.tsx DeveloperTask9.test.tsx && npm run typecheck`

Expected: PASS.

- [ ] **Step 7: Commit**

Commit message: `feat: redesign models activity and quickstart`

---

### Task 5: Redesign operator overview, providers, people, usage, and guardrails

**Files:**
- Modify: `frontend/src/ui/App.tsx`
- Modify: `frontend/src/ui/operator/MoneyRunway.tsx`
- Modify: files under `frontend/src/ui/operator/providers/`
- Modify: files under `frontend/src/ui/operator/people/`
- Modify: files under `frontend/src/ui/operator/usage/`
- Modify: `frontend/src/ui/operator/Guardrails.test.tsx`
- Modify: `frontend/src/ui/operator/ProviderTask8.test.tsx`
- Modify: `frontend/src/ui/styles.css`

**Interfaces:**
- Consumes: existing operator dashboard/provider/people/usage/guardrail APIs and actions.
- Produces: screenshot-density operator analytics with provider health/cost metadata where available and unchanged destructive-action confirmation behavior.

- [ ] **Step 1: Extend operator tests**

Cover role-safe navigation/action rendering, empty provider/incident states, and guardrail confirmations/state updates.

- [ ] **Step 2: Run focused operator tests and verify failures**

Run: `cd frontend && npm test -- Guardrails.test.tsx ProviderTask8.test.tsx`

- [ ] **Step 3: Recompose operator overview and usage**

Use compact metric cards, runway/allowance visualization, charts, top models/providers, and recent activity sourced from current APIs only.

- [ ] **Step 4: Recompose providers and people**

Use dense searchable tables/cards, compact tags/statuses, and existing controls without changing action semantics.

- [ ] **Step 5: Recompose guardrails/audit**

Group current controls into consistent panels/tabs while retaining confirmations and current backend payloads.

- [ ] **Step 6: Run operator tests and typecheck**

Run: `cd frontend && npm test -- Guardrails.test.tsx ProviderTask8.test.tsx && npm run typecheck`

Expected: PASS.

- [ ] **Step 7: Commit**

Commit message: `feat: redesign operator portal surfaces`

---

### Task 6: Responsive polish and full verification

**Files:**
- Modify: `frontend/src/ui/styles.css`
- Modify: only affected UI tests if verification exposes deterministic layout/state regressions.

**Interfaces:**
- Consumes: all redesigned surfaces.
- Produces: final runnable demo branch with 1920px-first composition and graceful 1280px behavior.

- [ ] **Step 1: Review the 1920px composition against the supplied screenshots**

Check grid alignment, sidebar proportion, card density, table row height, title/control scale, border/radius consistency, and unnecessary vertical scrolling.

- [ ] **Step 2: Review 1600px and 1280px desktop behavior**

Ensure secondary panels stack where needed and dense tables become horizontally scrollable instead of clipping.

- [ ] **Step 3: Run the complete frontend test suite**

Run: `cd frontend && npm test`

Expected: PASS.

- [ ] **Step 4: Run static verification**

Run: `cd frontend && npm run typecheck && npm run lint && npm run build`

Expected: all commands PASS.

- [ ] **Step 5: Inspect the final diff for backend-contract or fabricated-data regressions**

Confirm changes are frontend-focused and that no fake operational data ships by default.

- [ ] **Step 6: Commit**

Commit message: `chore: polish and verify pixel dashboard demo`
