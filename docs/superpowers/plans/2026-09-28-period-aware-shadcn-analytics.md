# Period-Aware Usage Analytics and shadcn Charts Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:subagent-driven-development` (recommended) or `superpowers:executing-plans`. Steps use checkbox syntax for tracking.

**Goal:** Make dashboard summaries, usage trends, and model-spend distribution accurate for a shared selected period, with a shadcn-style accessible chart system.

**Architecture:** Extend the role-scoped dashboard API with a typed analytics range, a timezone-aware period window, a complete per-model usage aggregation, and cost-coverage metadata. Keep the allowance runway on its independent server-computed monthly window. Render the range trend and spend-mix donut using a small local chart wrapper built from shadcn’s Recharts v3 composition patterns; retain our current CSS tokens rather than replatforming to Tailwind.

**Tech Stack:** FastAPI, Python 3.11+, SQLite, exact nano-USD event accounting, React 19, TypeScript, Recharts 3, Vitest/Testing Library, pytest.

**Spec:** `docs/superpowers/specs/2026-09-28-provider-catalog-and-analytics-design.md` (analytics window, API contract, chart semantics, access/privacy invariants).

## Global Constraints

- The default analytics window is `current_month`, with boundaries in `Europe/Berlin`; allowed ranges are `current_month`, `7d`, `30d`, and `90d`.
- One selected range drives the period-specific analytics summary, daily series, top-model ranking, and model-spend chart; preserve the existing all-time `usage` totals and label them Lifetime.
- The monthly allowance/reservation runway remains tied to its separate calendar-month limit and is not changed by the analytics selector.
- Developer dashboard aggregates only that developer; operator dashboard may aggregate service-wide. Never accept an owner ID from the client as authorization.
- Model-spend chart uses all models in the selected window, not the all-time `topModels` top-eight list. Historical usage uses stored model/provider/key snapshots, not joins to the active catalog.
- Monetary aggregations use integer nano-USD/event snapshots and return decimal USD strings. Missing cost/tokens are unknown, not zero/free.
- No prompt/completion storage or display. Preserve the currently deployed OpenAI-compatible routes and all existing controls.
- Charts use CSS-variable colors from the existing red/zinc theme; no rainbow-per-model palette, no page-level horizontal overflow, no sample chart data.

## Review Focus

1. Berlin month-start, DST transitions, leap February, year rollover, and inclusive/exclusive event bounds.
2. Per-model cost totals sum exactly to the selected range’s priced-spend total; unknown-cost events are visibly incomplete and never become free.
3. All model rows contribute to the denominator, including models beyond the current top-eight, and deleted models remain represented by usage snapshots.
4. Concurrent requests/reservations and provider/global/key/user budgets remain unchanged by analytics reads.
5. Developer and operator scopes do not leak across roles; charts remain usable with zero rows, partial tokens, unpriced cost, keyboard navigation, and reduced motion.

---

## File Map

- Modify `app/periods.py` — define a separate timezone-aware `DashboardRange`/`DashboardWindow` for chart/API requests without altering allowance-period semantics.
- Modify `app/portal_db.py` — period-bounded summary, daily series, and full per-model aggregation from usage snapshots.
- Modify `app/portal_api.py` — validate `range`, return one matching range envelope on developer/operator dashboards.
- Test `tests/test_portal_analytics.py` (new), `tests/test_portal_api.py`, and existing period/gateway tests.
- Modify `frontend/src/contracts/api.ts` and `frontend/src/lib/api.ts` — typed range and dashboard analytics response.
- Create `frontend/src/ui/charts/ChartContainer.tsx`, `UsageTrendChart.tsx`, and `ModelSpendChart.tsx` — local shadcn/Recharts composition adapted to current CSS.
- Modify `frontend/src/ui/App.tsx` and `frontend/src/ui/styles.css` — shared range selector and developer/operator analytics modules.
- Test `frontend/src/ui/UsageCharts.test.tsx` and `AnalyticsRange.test.tsx` (new), plus dashboard and operator API contract tests.
- Modify `frontend/package.json` and `frontend/package-lock.json` — add Recharts v3; do not run shadcn init or add Tailwind.

## Interfaces

```python
DashboardRange = Literal["current_month", "7d", "30d", "90d"]
@dataclass(frozen=True)
class DashboardWindow:
    range_key: DashboardRange
    start_utc: datetime
    end_utc: datetime
    timezone_name: str
dashboard_window(range_key: DashboardRange, now: datetime, timezone_name: str = "Europe/Berlin") -> DashboardWindow
```

```typescript
type DashboardRange = "current_month" | "7d" | "30d" | "90d";
interface ModelSpendRecord {
  modelId: string;
  providerName: string;
  requests: number;
  totalTokens: number | null;
  spendUsd: string | null;
}
interface AnalyticsWindow {
  range: DashboardRange;
  from: string;
  to: string;
  timezone: "Europe/Berlin";
}
interface DashboardAnalytics {
  window: AnalyticsWindow;
  summary: UsageSummary | null;
  series: UsagePoint[];
  topModels: ModelUsageRecord[];
  modelSpend: ModelSpendRecord[];
  knownSpendUsd: string | null;
  unpricedRequests: number;
}
```

Exact response field names may follow existing dashboard conventions, but both dashboard roles must return the same range/summary/series/model-spend semantics. Add `analytics` alongside the current all-time `usage`, `series`, and `topModels` fields so existing clients retain their behavior. The new portal charts consume only the matching period's `analytics` envelope; the client must not reconstruct billing totals from the truncated legacy list.

## Tasks

### Task 1: Pin range windows and database aggregation semantics

**Files:** `app/periods.py`, `app/portal_db.py`, `tests/test_portal_analytics.py`, `tests/test_periods.py`.

- [ ] **Step 1: Write failing range tests.** `current_month` begins at 00:00 Berlin time on day one and ends at captured `now`; `Nd` begins at 00:00 Berlin time N−1 local dates before today and ends at that same `now`. Test 7/30/90-day boundaries, DST, leap February, and December/January.
- [ ] **Step 2: Run tests to prove missing behavior** — `py -3.11 -m pytest tests/test_portal_analytics.py tests/test_periods.py -q -p no:cacheprovider`.
- [ ] **Step 3: Write failing DB tests.** Seed events before/inside/after the range for multiple users, provider brands, keys, deleted-model snapshots, partial token data, and unknown prices. Assert exact nano-USD totals, all models included, and owner scoping.
- [ ] **Step 4: Add `dashboard_window` and one reusable range predicate.** Use `occurred_at >= start` and `occurred_at < end`; normalize UTC timestamps, but compute calendar boundaries in Europe/Berlin.
- [ ] **Step 5: Add period-scoped summary/series/model aggregation.** Return every model’s recorded cost or null; count events with no known cost separately; keep reservations out of settled model-spend distribution and keep allowance reservation accounting unchanged.
- [ ] **Step 6: Run analytics and existing budget tests; verify model-spend rows reconcile to exact known spend.**

### Task 2: Expose role-scoped dashboard range API

**Files:** `app/portal_api.py`, `tests/test_portal_analytics.py`, `tests/test_portal_api.py`.

- [ ] **Step 1: Write failing API tests.** Developer `range` queries see only their account; operator queries are global; missing range defaults to `current_month`; invalid range returns 422; the analytics window metadata exactly matches the events aggregated into its summary, series, and breakdown.
- [ ] **Step 2: Add typed query validation to `/api/developer/dashboard` and `/api/operator/dashboard`.** Do not add a caller-selectable `owner_user_id` for developer routes.
- [ ] **Step 3: Add an `analytics` response envelope with selected-window summary, series, period top models, complete `modelSpend`, known-spend total, and unpriced-event coverage.** Preserve the existing lifetime `usage`/`series`/`topModels` response fields for compatibility; preserve `allowance` as its separate monthly value and maintain key/provider/global policy APIs.
- [ ] **Step 4: Run API and full backend tests** — `py -3.11 -m pytest -q -p no:cacheprovider`.

### Task 3: Add shadcn-compatible local chart primitives

**Files:** `frontend/package.json`, `frontend/package-lock.json`, `frontend/src/ui/charts/ChartContainer.tsx`, `frontend/src/ui/styles.css`, `frontend/src/ui/UsageCharts.test.tsx`.

- [ ] **Step 1: Add failing component tests** for responsive sizing, accessible labeling, tooltip/legend values, and reduced-motion-safe empty state.
- [ ] **Step 2: Add Recharts v3 and verify React 19 compatibility from the resolved lockfile.** Use the shadcn composition patterns (`ChartContainer`, `ChartTooltipContent`, `ChartLegendContent`, `accessibilityLayer`) implemented as local React/CSS components; do not introduce Tailwind or the shadcn CLI scaffold.
- [ ] **Step 3: Define a restrained chart token palette** from the current zinc/red CSS variables and confirm contrast for labels, grid, tooltip, and focus.
- [ ] **Step 4: Run the focused chart tests and frontend typecheck.**

### Task 4: Render selected-period trends and model-spend mix

**Files:** `frontend/src/contracts/api.ts`, `frontend/src/lib/api.ts`, `frontend/src/ui/App.tsx`, `frontend/src/ui/charts/UsageTrendChart.tsx`, `frontend/src/ui/charts/ModelSpendChart.tsx`, `frontend/src/ui/styles.css`, `frontend/src/ui/AnalyticsRange.test.tsx`.

- [ ] **Step 1: Add failing UI tests** for range controls/default month, synchronized period summary/trend/model mix, clearly labeled unchanged lifetime totals, and independent allowance period.
- [ ] **Step 2: Add a shared period selector** for This month, Last 7 days, Last 30 days, and Last 90 days. Serialize as the API range query; show the selected range in headings/labels.
- [ ] **Step 3: Implement an accessible trend chart** with request/token/spend series, units, daily tooltip, and empty/loading/error states.
- [ ] **Step 4: Implement the spend donut.** Calculate percentages and the `<3%` cutoff from decimal USD strings using integer/BigInt arithmetic (add a tested basis-point helper if needed); do not sum binary floats for the displayed total. Group each model below 3% into Other models; show percent in legend and exact amount+percent in tooltip. If any request has unknown cost, label the chart as known/priced spend and expose coverage; if total cannot be reconciled, render an incomplete state instead of a misleading full chart.
- [ ] **Step 5: Add a screen-reader data table for both charts; preserve the model usage table, recent activity, provider health, guardrail, and allowance sections.**
- [ ] **Step 6: Run focused UI/API tests and `npm run lint && npm run typecheck`.**

### Task 5: Cross-surface verification and handoff

- [ ] Run backend full suite, frontend full suite, lint, typecheck, and production build.
- [ ] Verify month boundaries in Europe/Berlin and range parity across developer/operator APIs.
- [ ] Verify provider/key/global cap enforcement and allowance remain unchanged; no model/key deletion erases historic series/breakdown records.
- [ ] Review at 1440px, 768px, and 390px; no page-level horizontal overflow, all chart legend/data remains reachable.
- [ ] Run a fresh `frontend-design-review` and read-only backend/API review; resolve critical/important findings before promotion.
- [ ] Do not deploy until the owner reviews the plan and explicitly authorizes the cutover; preserve backup/rollback and one-worker SQLite operation.

## Skills and Subagent Plan

- **Backend/API agent:** GPT-6 Luna medium, owns `app/periods.py`, `app/portal_db.py`, `app/portal_api.py`, and backend tests; use TDD, software architecture review, and verification-before-completion.
- **Frontend agent:** GPT-6 Luna medium, sole writer to `frontend/**` across the catalog and analytics work; use `frontend-design`, `mobile-responsiveness`, `accessibility`, `kpi-dashboard-design`, and TDD. Keep the two plans' shared `App.tsx`/`styles.css` edits in this single frontend stream.
- **Review:** fresh GPT-6 Luna medium frontend/API reviewers; use `frontend-design-review`, `critique`, and `verification-before-completion`.
- The session has a React/Vite app, not a distinct “Poorup frontend” package; Poorup-specific rules remain scoped to that other repo. No broad shadcn/Tailwind migration, anti-slop plugin install, image assets, or new animation system is in scope.
