# Hack Club AI-inspired Portal Redesign Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development to implement this plan task-by-task. Steps use checkbox syntax for tracking.

**Goal:** Restyle every operator and developer portal view with Hack Club AI's verified zinc/red visual language and content rhythm while retaining Sponsored Provider's role, privacy, model, and budget behavior.

**Architecture:** Keep the current React/Vite SPA, Radix primitives, API contracts, and route boundaries. Replace the shared shell and tokens first, then adapt developer and operator page composition to HCAI's compact header, statistic strip, cards, model browse, and quickstart patterns. Do not copy HCAI identity or add its unrelated features.

**Tech Stack:** React 19, Vite, TypeScript, Radix UI, Lucide, CSS variables, Vitest/Testing Library.

**Spec:** `.ulpi/design/hackclub-ai-portal-refresh.md` and `.ulpi/design/DESIGN.md`.

## Global Constraints

- Keep local username/password authentication, invite-only access, role authorization, provider catalog, `/v1` compatibility, and all current safeguard behavior.
- Keep Hack Club Auth routes/UI dormant; do not copy HCAI's OAuth, shared key model, or unrelated image/Replicate features.
- Never show upstream credentials, prompt/completion content, or another developer's activity/IP.
- Show estimated versus reported amounts and input/output tokens distinctly; no missing usage rendered as zero/free.
- Use the locked zinc/red palette, HCAI geometry, one Radix/Lucide vocabulary, and keyboard/reduced-motion behavior from the design spec.
- Nest currently has Node `20.18.1`, below this Vite version's `20.19+` requirement; use a validated supported local Node build and transfer `frontend/dist`, or explicitly upgrade the build runtime before relying on an on-Nest build.
- Preserve one top-level navigation with role-specific links; no role mixing or new permission surface.
- The separate $7 monthly per-developer allowance migration is owned by `2026-09-27-monthly-developer-allowance.md`; this plan may consume its API contract but must not invent a second budget calculation.

## Review Focus

1. Same-origin user and operator routes must not leak data when changing route IDs or using browser back/refresh.
2. Small red-on-charcoal text must use the accessible accent-text token; the exact HCAI red is not readable as small text on its dark surface.
3. Provider/user tables and filters must remain usable at 390px without clipped actions or hidden state.
4. Empty, stale, partial/unknown, error, loading, and success views must preserve the distinction between unreported and zero usage.
5. HCAI styling must not re-enable Hack Club OAuth or expose its global/other-user statistics to developers.

---

## File Map

- `frontend/src/ui/styles.css` — sole visual token source, responsive layout, controls, status, and shared shell styles.
- `frontend/src/ui/App.tsx` — role-specific shell, navigation, operator overview/people/guardrails, developer home/keys/quickstart.
- `app/main.py` — only if Google Sans must be loaded from Google Fonts; update CSP with exact `fonts.googleapis.com`/`fonts.gstatic.com` sources and add a header regression test. Prefer a permitted self-hosted font if available.
- `frontend/src/ui/developer/ModelCatalogPage.tsx` and `DeveloperActivityPage.tsx` — catalog and personal activity page hierarchy.
- `frontend/src/ui/operator/providers/*.tsx`, `operator/usage/OperatorUsagePage.tsx`, `operator/people/AllowanceEditor.tsx` — operator table/detail surfaces.
- `frontend/src/ui/AuthPage.tsx` — same local-account and invitation behavior with the refreshed visual system.
- `frontend/src/contracts/api.ts`, `frontend/src/lib/api.ts` — only when a page needs an existing API field; monthly allowance types remain owned by the allowance plan.
- `frontend/src/ui/*test.tsx` — semantic interaction and role-boundary tests.
- `.ulpi/design/DESIGN.md` — locked project tokens; `.ulpi/design/hackclub-ai-portal-refresh.md` remains the page/state specification.

## Tasks

### Task 1: Shared shell and HCAI visual tokens

**Files:**
- Modify: `frontend/src/ui/styles.css`
- Modify: `frontend/src/ui/App.tsx`
- Test: create `frontend/src/ui/PortalShell.test.tsx`

**Interfaces:** Keep `PortalRole = "developer" | "operator"`, `developerNav`, `operatorNav`, and current React Router paths. Extract a `PortalShell` only if that gives tests a stable role-navigation surface without changing route semantics.

- [ ] **Step 1: Add failing shell tests** — assert role-specific links, active route, account/logout control, skip link, and mobile menu state; test both `preview=developer` and `preview=operator` without rendering sample metrics.
- [ ] **Step 2: Run the shell tests and verify the intended failure** — `cd frontend && npm test -- --run src/ui/PortalShell.test.tsx`.
- [ ] **Step 3: Replace the left rail with the compact HCAI-inspired top header** — preserve operator/developer navigation separation; use the red logo mark and account context but not the HCAI logo/name.
- [ ] **Step 4: Replace global tokens and shell geometry** — background `#18181b`, surface `#27272a`, primary `#ec3750`, hover `#d62640`, heading `#fafafa`, body `#d4d4d8`, subtle border `#303035`; content `max-w-6xl px-4 py-8`, header `max-w-7xl px-4 py-6`.
- [ ] **Step 5: Resolve font delivery before changing CSP** — prefer a license-permitted self-hosted face; if using the reference's Google Fonts delivery, allow only the exact stylesheet/font origins and verify no broader CSP source is added.
- [ ] **Step 6: Verify** — shell tests and `npm run typecheck`; confirm the only source of component colors is the token layer and any CSP change is narrow.
- [ ] **Step 7: Commit** — `style: adopt Hack Club AI console visual system`.

### Task 2: Developer home, API keys, model catalog, and quickstart

**Files:**
- Modify: `frontend/src/ui/App.tsx`
- Modify: `frontend/src/ui/developer/ModelCatalogPage.tsx`
- Modify: `frontend/src/ui/developer/DeveloperActivityPage.tsx`
- Modify: `frontend/src/ui/developer/AllowanceSummary.tsx`
- Test: `frontend/src/ui/DeveloperTask9.test.tsx`, `DeveloperKeyDialog.test.tsx`, new `DeveloperHome.test.tsx`

**Interfaces:** Use the existing `PortalApi` and existing request/model/key records. Consume the monthly allowance fields from the monthly allowance plan; do not introduce another local spend calculation.

- [ ] **Step 1: Add failing tests** — home stat strip plus first-call snippet; key table shows policy/reset/state; catalog shows provider-qualified IDs and verified prices; activity shows input/output, estimated cost, result, and latency; no prompt/response text or other-user data.
- [ ] **Step 2: Run each new test to verify failure** — `cd frontend && npm test -- --run src/ui/DeveloperHome.test.tsx src/ui/DeveloperTask9.test.tsx src/ui/DeveloperKeyDialog.test.tsx`.
- [ ] **Step 3: Implement HCAI-style developer hierarchy** — compact 2-up mobile/4-up wide stat strip, quick links, copyable OpenAI example, card/list model browsing, and paginated activity table. Keep provider attribution, capability, token/cost provenance, selected model policy, and the personal $7/month runway.
- [ ] **Step 4: Implement loading/empty/stale/unknown/error states** — unknown remains “Not reported”; empty usage teaches how to make the first call; no fictitious values.
- [ ] **Step 5: Verify** — run the focused tests and API contract tests in `frontend/src/lib/developerApi.contract.test.ts`.
- [ ] **Step 6: Commit** — `feat: refresh developer portal for first-call workflow`.

### Task 3: Operator overview, people, providers, usage, and guardrails

**Files:**
- Modify: `frontend/src/ui/App.tsx`
- Modify: `frontend/src/ui/operator/people/AllowanceEditor.tsx`
- Modify: `frontend/src/ui/operator/providers/*.tsx`
- Modify: `frontend/src/ui/operator/usage/OperatorUsagePage.tsx`
- Test: `frontend/src/ui/operator/ProviderTask8.test.tsx`, new `OperatorShell.test.tsx`

**Interfaces:** Use the existing operator API types. The current UI remains an operator-only view; account allowance values and period come from the server.

- [ ] **Step 1: Add failing tests** — global runway labels/reservations, provider sync health and pricing provenance, people rows with shared allowance, key/model/IP quick actions, confirmation of high-impact actions, and role-only nav.
- [ ] **Step 2: Run the focused operator tests to verify failure** — `cd frontend && npm test -- --run src/ui/operator/ProviderTask8.test.tsx src/ui/operator/OperatorShell.test.tsx`.
- [ ] **Step 3: Implement operator hierarchy** — overview stat strip, global/provider runway, health and recent activity; table-first People, Providers, and Usage; contextual detail sheets; clearly separate the $7 user allowance from global and upstream connection hard stops.
- [ ] **Step 4: Keep sensitive controls protected** — provider credentials stay write-only; disable/revoke/block/global-stop actions retain confirm/recovery; no prompt display.
- [ ] **Step 5: Verify** — focused UI tests plus `frontend/src/lib/operatorApi.contract.test.ts`.
- [ ] **Step 6: Commit** — `feat: refresh operator portal for sponsored usage operations`.

### Task 4: Sign-in polish and responsive/error states

**Files:**
- Modify: `frontend/src/ui/AuthPage.tsx`
- Modify: `frontend/src/ui/styles.css`
- Test: `frontend/src/ui/AuthPage.test.tsx`, `InviteComponents.test.tsx`

- [ ] **Step 1: Add failing tests** — local sign-in/signup toggle, invite-required signup, password visibility control, validation/error feedback, focus order, and mobile viewport safe areas.
- [ ] **Step 2: Run focused auth tests to verify failure** — `cd frontend && npm test -- --run src/ui/AuthPage.test.tsx src/ui/InviteComponents.test.tsx`.
- [ ] **Step 3: Apply the HCAI visual language without changing auth behavior** — retain username/password and invite gate; do not add OAuth.
- [ ] **Step 4: Verify** — focused tests and `npm run typecheck`.
- [ ] **Step 5: Commit** — `style: align local auth with portal design system`.

### Task 5: Cross-surface verification and handoff

- [ ] Run `cd frontend && npm test`, `npm run lint`, `npm run typecheck`, and `npm run build`.
- [ ] Capture and inspect authenticated/preview views at 1440px, 768px, and 390px; include operator and developer routes plus auth.
- [ ] Run the Impeccable detector once over changed UI files; resolve mechanical findings.
- [ ] Run a fresh `frontend-design-review` over screenshots and changed components; focus on HCAI fidelity, no cross-role leakage, contrast, focus, overflow, and empty/error states.
- [ ] Build static assets with supported Node 24 (or a verified `20.19+` runtime); deploy the exact built `frontend/dist` artifact and smoke-test hashed JS/CSS behind Nest's CSP.
- [ ] Verify no old yellow/navy token remains except intentional semantic/status assets; verify the local/password auth routes stay active and HCA routes stay dormant.
- [ ] After rendered review passes, update the canonical `DESIGN.md` from the shipped styles via Impeccable's documenter; do not promote proposal-only tokens before review.
- [ ] Commit any review fixes; do not publish/deploy before the full plan and tests are reviewed.

## Skills and Subagent Plan

- **Planning/design:** `superpowers:brainstorming`, Impeccable `shape`, and `frontend-design-ui-ux` maintain the design spec and locked token source. The source repo itself was inspected for geometry and color; no third-party assets or HCAI branding are copied.
- **Implementation:** `frontend-design` plus `mobile-responsiveness` for React/CSS and phone layout; TDD for each interaction/state.
- **Review:** `frontend-design-review` for insight-to-action, quality craft, trust, keyboard, contrast, and responsive behavior; `kpi-dashboard-design` for metric hierarchy/definitions; `superpowers:verification-before-completion` before promotion.
- **Finish:** after the rendered system is reviewed, run Impeccable's documenter/update the global `DESIGN.md` from the shipped UI; do not claim the new token lock is final before that review.
- **Not applicable:** `design-taste-frontend` explicitly excludes dashboards/data-table product UI; the product-focused design/review skills above are the fit. No new anti-slop package, image assets, or motion system is needed for this content-led console refresh.
- **Agent split after approval:** one GPT‑6 Luna medium agent owns `frontend/` only; one GPT‑6 Luna medium agent owns the monthly allowance backend/API/tests only; a fresh GPT‑6 Luna medium reviewer performs the integrated UI/API review. Keep write sets disjoint; the orchestrator owns interfaces, final integration, and deployment.
- **Current planning constraint:** the agent service reported its active-thread limit during this planning turn; no subagents were spawned. Use the above delegation after capacity is available, or tell the user before substituting an in-thread implementation.
- **Not used:** `design-taste-frontend` explicitly excludes dashboards/data tables, so it is not a fit for these authenticated product screens. Motion stays restrained; use an animation-specific skill only if the brief later adds expressive motion.
