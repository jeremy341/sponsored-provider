# Provider Model Catalog and Detail Experience Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:subagent-driven-development` (recommended) or `superpowers:executing-plans`. Steps use checkbox syntax for tracking.

**Goal:** Turn the provider-grouped model list into a fast, responsive catalog with shareable model-detail pages and correct code examples.

**Architecture:** Keep React Router and the existing approved-model API. Cards link to a deep route whose wildcard preserves provider-scoped IDs containing slashes. Pass a selected record and catalog filters through navigation state for fast in-app transitions; on refresh/direct entry, load the approved catalog and resolve the same public ID. No provider request, secret, or model policy is changed by browsing.

**Tech Stack:** React 19, React Router 7, TypeScript, Radix UI, CSS design tokens, Vitest/Testing Library.

**Spec:** `docs/superpowers/specs/2026-09-28-provider-catalog-and-analytics-design.md` (model catalog, routing, metadata, examples, preservation invariants).

## Global Constraints

- Keep one public card per provider-brand/canonical-model offer; merge same-brand routes and keep different brands distinct.
- The detail route must support public IDs containing `::` and `/`; no ambiguous single path parameter.
- Only render metadata and prices present in the approved catalog record; unknown technical data stays omitted or “Not reported.”
- Code samples use the same-origin `/v1` endpoint, selected public model ID, and a placeholder API key only.
- Do not show upstream credentials, base URLs, prompts/completions, or unapproved models.
- Preserve developer/operator separation, filters, price provenance, mobile layout, and access policy.

## Review Focus

1. Direct load/refresh/back behavior for slash-containing provider-scoped IDs and stale/unpublished models.
2. Cross-brand duplicate IDs remain distinct; same-brand alternate routes do not produce duplicate cards.
3. Unknown/hidden metadata must not be fabricated; unverified prices must not appear usable.
4. Copy buttons remain separate semantic controls from card links; keyboard/focus behavior remains valid.
5. Example code must match the actual `/v1/chat/completions` contract and never include a live secret.

---

## File Map

- Modify `frontend/src/ui/App.tsx` — add the `/developer/models/*` detail route.
- Modify `frontend/src/ui/developer/ModelCatalogPage.tsx` — provider groups, compact cards, deep links, filter-state preservation.
- Create `frontend/src/ui/developer/ModelDetailPage.tsx` — model identity, verified price/metadata summary, code tabs, safe unavailable state.
- Create `frontend/src/ui/developer/ModelCodeExamples.tsx` — shared language tabs, snippet construction, and copy state.
- Modify `app/portal_db.py` and `app/portal_api.py` — serialize a verified aggregate active-route count without exposing route internals.
- Modify `frontend/src/contracts/api.ts` — add nullable `activeRouteCount` to `ModelRecord`.
- Modify `frontend/src/ui/styles.css` — card grid, detail layout, responsive states using current tokens.
- Test `tests/test_portal_db_catalog.py`, `tests/test_portal_api.py`, `frontend/src/ui/developer/ModelCatalogPage.test.tsx`, and `frontend/src/ui/developer/ModelDetailPage.test.tsx`; extend `DeveloperTask9.test.tsx` only where current test helpers fit.

## Tasks

### Task 1: Expose safe route-count metadata

**Files:**
- Modify: `app/portal_db.py`
- Modify: `app/portal_api.py`
- Test: `tests/test_portal_db_catalog.py`, `tests/test_portal_api.py`

**Interfaces:** Normalized published model rows gain `active_route_count: int | None`; `_api_model(..., public_id=True)` serializes `activeRouteCount: number | null`. Legacy rows without route metadata return `null`.

- [ ] **Step 1: Write failing repository/API tests** — same-brand offers report the number of eligible active routes; disabled, stale, unhealthy, or price-mismatched routes are not counted; developer response exposes only the number, never connection IDs, private labels, base URLs, or credentials.
- [ ] **Step 2: Run tests to verify the intended failure** — `py -3.11 -m pytest tests/test_portal_db_catalog.py tests/test_portal_api.py -q -p no:cacheprovider`.
- [ ] **Step 3: Implement the aggregate count from the offer's eligible route set.** Do not add route labels or a new credential-bearing response shape.
- [ ] **Step 4: Rerun focused backend tests and diff-check.**

### Task 2: Pin card and detail-route behavior

**Files:**
- Modify: `frontend/src/contracts/api.ts`
- Create: `frontend/src/ui/developer/ModelCatalogPage.test.tsx`
- Create: `frontend/src/ui/developer/ModelDetailPage.test.tsx`

**Interfaces:** Add `ModelRecord.activeRouteCount: number | null` to the frontend contract for the backend field produced by Task 1; all other model reads continue through `PortalApi.listModels()`.

- [ ] **Step 1: Add the nullable `activeRouteCount` API type and test fixtures.**
- [ ] **Step 2: Write failing catalog tests** — provider-group headings; existing search/capability/price filters; card shows public ID, capability, verified input/output/cached prices and route count when known; copy action is separate from the detail link.
- [ ] **Step 3: Write failing route tests** — an ID such as `nebula::deepseek/deepseek-v4-flash` resolves on direct load, preserves catalog filters on return, and an unknown/unpublished ID shows a safe unavailable state.
- [ ] **Step 4: Run focused tests to verify the intended failures** — `cd frontend && npm test -- --run src/ui/developer/ModelCatalogPage.test.tsx src/ui/developer/ModelDetailPage.test.tsx`.

### Task 3: Build the responsive card catalog and deep-link route

**Files:**
- Modify: `frontend/src/ui/App.tsx`
- Modify: `frontend/src/ui/developer/ModelCatalogPage.tsx`
- Create: `frontend/src/ui/developer/ModelDetailPage.tsx`
- Modify: `frontend/src/ui/styles.css`

**Interfaces:** Detail route is `/developer/models/*`; read the React Router splat as the exact public model ID. Carry the record and filter state through navigation state; on refresh/direct entry, call `PortalApi.listModels()` and match `ModelRecord.id` exactly.

- [ ] **Step 1: Make each card a semantic article with one detail link and an independent copy-ID button.** Do not nest interactive elements.
- [ ] **Step 2: Group by provider brand, show a compact responsive card grid and route-count badge when known, and cap each group’s initial phone preview with an accessible “Show all/Show less” control.** Preserve search, provider/capability facets, and price sort.
- [ ] **Step 3: Add the detail route and a “Back to models” link that restores the catalog search/filter query.** Handle a deleted/unpublished model without changing key state or making it routable.
- [ ] **Step 4: Verify card and route tests pass.**

### Task 4: Add model detail hierarchy and code examples

**Files:**
- Create: `frontend/src/ui/developer/ModelCodeExamples.tsx`
- Modify: `frontend/src/ui/developer/ModelDetailPage.tsx`
- Modify: `frontend/src/ui/styles.css`
- Test: `frontend/src/ui/developer/ModelDetailPage.test.tsx`

**Interfaces:** Reuse existing `ModelRecord` fields: provider, public ID, capabilities, availability, verified rates/source, and sync time. Technical fields not in the current record are not fabricated or added in this plan.

- [ ] **Step 1: Add failing tests for the detail summary** — provider/capability, public ID copy, verified input/output/cache rates and provenance; unknown cache price is “Not reported.”
- [ ] **Step 2: Implement the model hero and price strip.** Keep cache price visually distinct; include availability and sync status where present.
- [ ] **Step 3: Add cURL, Python OpenAI SDK, and JavaScript OpenAI SDK examples.** All use the selected model ID, `${window.location.origin}/v1`, and `YOUR_API_KEY`; no secret is copied or persisted.
- [ ] **Step 4: Only show a vision example for a `vision` capability and after a frontend/API contract test confirms image-input forwarding; otherwise show the supported text chat example.** Do not show unsupported embedding or image-generation endpoints.
- [ ] **Step 5: Add keyboard-operable tabs, copy confirmation, syntax-readable code blocks with internal horizontal scrolling, and reduced-motion-compatible transitions; rerun the detail tests.**

### Task 5: Verify catalog behavior and responsive layout

- [ ] Run focused tests, the full frontend suite, lint, typecheck, and production build.
- [ ] Inspect catalog and detail routes at 1440px, 768px, and 390px, including long model IDs, provider names, and code-block overflow.
- [ ] Verify browser Back and direct refresh restore the route and catalog filters.
- [ ] Verify no key policy, provider credential, or request prompt/completion appears in developer responses or the detail page.

## Subagent and Skill Plan

- Use one GPT-6 Luna medium frontend worker as the sole writer to `frontend/**` across both catalog and analytics plans; keep the two surfaces coordinated and avoid competing edits to `App.tsx`/`styles.css`.
- Apply `frontend-design`, `mobile-responsiveness`, `accessibility`, and `superpowers:test-driven-development` to implementation; use a fresh `frontend-design-review` reviewer for the integrated branch.
- Use a read-only `critique` pass against the rendered cards/detail page. No new motion system or anti-slop package is planned.
- A separate GPT-6 Luna medium backend worker owns only the analytics API/data task from the companion plan.
