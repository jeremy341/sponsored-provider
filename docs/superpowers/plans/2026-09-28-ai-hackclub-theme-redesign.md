# Plan: Portal redesign → ai.hackclub.com console + retro pixel layer + legacy dashboard removal

**Status:** planning only — no code written; only this file exists.
**Date:** 2026-09-28 · **Revision:** v2 (supersedes v1 of this same file) · **Mode:** Operate · **Scope:** React portal restyle **+ delete the legacy Control Room**.

## 0. Locked decisions

| Decision | Answer |
|---|---|
| Reference | `https://ai.hackclub.com` — layout, colors, icons, type scale (screenshots supplied: dashboard, model detail, activity) |
| Retro layer | **VT323** for display numbers ≥18px + **Silkscreen** for 11–12px uppercase micro-labels; body stays Noto Sans, code/table numerals stay Maple Mono |
| Retro surface cue | **Stepped/dithered progress bars only** (with numeric % retained). Scanline, notched corners, square-cap icons, CRT flicker: rejected this round |
| Theming | Dark only, reference dark palette. No light mode, no toggle |
| Legacy dashboard | **Full removal**: `app/static/`, `/dashboard`, `/static` mount, `/api/dashboard`, all `/api/admin/*`, `require_admin`, `admin_token` config/secret. **All five legacy DB tables stay** |
| Design authority | `.ulpi/design/DESIGN.md` rewritten to this direction; Poorup pixel lock superseded; `hackclub-ai-portal-refresh.md` (zinc/red) marked superseded |
| Non-goals | No `/v1`, auth, session, CSRF, budget, routing, model-approval behavior changes; no Tailwind/shadcn; no new UI or icon library; no light mode; no landing page; no deploy/cutover; no commit/push without explicit request |

**Binding constraints:** self-hosted fonts only (CSP `font-src 'self'` — no CDN/Google Fonts); keep Radix + Recharts + Lucide; WCAG 2.2 AA; money semantics preserved ("estimated/unknown" never renders as zero/free); one-time secret reveal; no prompt storage.

> **Scope note:** this revision is the one place a backend change is authorized — the legacy dashboard removal in Task 1. Everything else in the plan is `frontend/` only. The backend carve-out is limited to routes/config listed in Task 1; `app/portal_api.py`, `app/portal_db.py` and `/v1` logic stay untouched.

## 1. Direction

**Thesis:** Ship an Ayu-dark IDE console — fixed left rail, 56px command bar, hairline dense tables, one amber accent — and spend the retro budget in exactly two places: bitmap type for numbers and micro-labels, and stepped progress bars. Retro is a signal, not a costume; Operate-mode scanability outranks expression.

**Kept from the current portal:** route topology and IA, honest-data discipline (`Not reported` ≠ 0, `gateway_estimate` vs `provider_reported`), `useLoad`/`?preview=` patterns, cursor pagination + filter toolbars, copy affordances, skip link, `aria-live` announcements, Radix dialog semantics, sr-only chart tables, the 15-file test suite.

**Rejected from the reference:** logo, name, copy, OAuth, `/proxy/v1` (per the audit in `docs/superpowers/specs/2026-09-28-provider-catalog-and-analytics-design.md`), its light theme, and its green-free status palette *only where our semantics need it*.

## 2. Design system spec (the new `.ulpi/design/DESIGN.md`)

### 2.1 Color tokens (dark only)

```css
:root {
  color-scheme: dark;
  --background: #0b0e14;   --card: #0d1017;   --popover: #0f131a;
  --sidebar: #0f131a;      --sidebar-border: #11151c;
  --secondary: #131721;    --muted: #131721;  /* hover/active fills, chips, code bg */
  --foreground: #bfbdb6;   /* warm gray, never #fff */
  --muted-foreground: #7d8595; /* AA-corrected from reference #6c7380 (3.99:1 on card) */
  --quiet-foreground: #6c7380; /* ≥19px or disabled only */
  --primary: #e6b450;      --primary-foreground: #0b0e14;
  --primary-hover: color-mix(in srgb, #e6b450 85%, #0b0e14);
  --primary-soft: rgb(230 180 80 / .10);
  --primary-soft-border: rgb(230 180 80 / .30);
  --destructive: #d95757;  --destructive-text: #f08a80;
  --success: #aad94c;      /* "available/approved" chips only */
  --info: #59c2ff;
  --border: rgb(71 82 102 / .35);   /* dividers only (1.27:1) */
  --border-strong: #5a6478;         /* control outlines, ≥3:1 */
  --input: rgb(71 82 102 / .45);
  --ring: #e6b450;
  --chart-1: #e6b450; --chart-2: #59c2ff; --chart-3: #aad94c;
  --chart-4: #d2a6ff; --chart-5: #f07178; --chart-grid: rgb(71 82 102 / .35);
}
```

- **OK/status = amber** (reference-faithful); errors red; green survives only for "available/approved" model chips so amber stays reserved for action + active state.
- Two reference values are corrected for AA: `--muted-foreground` `#6c7380`→`#7d8595` (5.13:1 on card) and a new `--border-strong #5a6478` for input/select/button outlines.
- All **~50 hardcoded hex occurrences** outside `:root` (status pills, notices, provider icons, model chips, preview banner, chart callouts) become tokens.

### 2.2 Typography — the retro layer

```css
@import "@fontsource-variable/noto-sans";   /* body */
@import "@fontsource/maple-mono/400.css";
@import "@fontsource/maple-mono/500.css";   /* code, IDs, table numerals */
@import "@fontsource/vt323/400.css";        /* display numbers ≥18px */
@import "@fontsource/silkscreen/400.css";
@import "@fontsource/silkscreen/700.css";   /* micro-labels 11–12px */

--font-body: "Noto Sans Variable", system-ui, sans-serif;
--font-mono: "Maple Mono", "IBM Plex Mono", ui-monospace, monospace;
--font-display: "VT323", var(--font-mono);   /* ≥18px ONLY */
--font-label: "Silkscreen", var(--font-mono);/* 11–12px uppercase ONLY */
```

All four packages verified present on the Fontsource/npm registry, SIL OFL, bundled into `dist` (CSP-safe).

| Face | Where it is used | Rules |
|---|---|---|
| **VT323** `--font-display` | Stat-strip values (24px), model-detail fact values, dashboard hero numbers, runway/allowance amounts, big money figures | **Only ≥18px.** Amber or `--foreground`. VT323 has a low x-height — never below 18px, never for sentences |
| **Silkscreen** `--font-label` | Eyebrows, table `th`, status chip text, nav section labels, badge/step numerals, "Jump to"/"Quickstart" section kickers, pill label | **Only 11–12px, uppercase, `letter-spacing: .06em`.** Contrast ≥4.5:1 (`--foreground` or `--primary`; `--muted-foreground` only if verified ≥4.5 at 11px — otherwise promote) |
| **Noto Sans** `--font-body` | All paragraphs, descriptions, form labels, inputs, buttons, table cells, dialogs | Default everywhere |
| **Maple Mono** `--font-mono` | Model IDs, key prefixes, request IDs, base URLs, code blocks, timestamps, dense numeric table cells, tooltips | `font-variant-numeric: tabular-nums` where numbers align |

**Never in a pixel face:** table cells, body copy, inputs, error/help text, long button labels, tooltips, anything <11px, italics.

Type scale (unchanged from reference): h1 `24px/600` · section h2 `14px/500` muted · body `14px` · muted description `14px` capped `62ch` · micro `12px`. Large stat numbers are the one place VT323 replaces the scale's `24px/600` — same size, display face.

### 2.3 Geometry, spacing, motion

- Radius: `--radius-sm .27rem` · `md .36rem` · `lg .45rem` (cards/tables/inputs) · `xl .63rem` · `pill 999px` (spend pill, chips, avatar only). **Pill buttons die.** Borders always `1px`; kill the `2px` sections.
- Shadow: `0 1px 2px rgb(0 0 0/.05)` on cards/inputs/tabs/code; dialog `0 20px 52px rgb(0 0 0/.72)`; overlay `rgb(0 0 0/.72)`.
- Motion: `--transition: 150ms cubic-bezier(.4,0,.2,1)` (color only), `--transition-shell: 150ms cubic-bezier(.23,1,.32,1)` (sidebar/dialog/sheet). No lift, scale, glow, gradient, or animated scanline. One `prefers-reduced-motion` block (today it is declared twice).
- Focus: `outline: 2px solid var(--ring); outline-offset: 2px` + `box-shadow: 0 0 0 4px rgb(230 180 80/.28)`; amber-filled controls switch outline to `#bfbdb6`. `scroll-margin-top: 64px`.
- Breakpoints: nine → four (`480`, `767`, `1024`, `1440`).

**Retro cue — stepped progress bars** (the only adopted surface cue): allowance runway, money runway, per-connection budgets, and key spend caps render as a **hard-edged dithered track**:

```css
.runway-fill {
  background: repeating-linear-gradient(90deg,
    var(--primary) 0 6px, rgb(230 180 80 / .55) 6px 8px);
  image-rendering: pixelated;   /* crisp on fractional widths */
}
```
Track = `--secondary` with a 1px `--border-strong` rule; the numeric percentage/amount **stays visible as text** (WCAG 1.4.11 + 1.4.1), and the bar keeps `role="progressbar"` with `aria-valuenow/min/max`. Over-cap fills switch to `--destructive`. No animation of the fill.

Rejected this round (recorded so they don't creep back): CRT scanline/vignette, notched `clip-path` corners, square-cap Lucide restyling, `steps()` animation, `-webkit-font-smoothing: none` (macOS-only, damages contrast).

### 2.4 Shell

- **Left rail 16rem**, `--sidebar` fill, 1px `--sidebar-border` right edge. Nav items `h-8 gap-2 rounded-md`, 16px Lucide glyph, `text-sm`; active = `--secondary` fill + `font-medium` + amber glyph + `aria-current="page"`. Section labels in `--font-label` 11px uppercase. Footer: avatar + name/email + chevron → **Sign out**.
- **Collapse** to 3rem icon rail, persisted (`provider.sidebar.collapsed`), `aria-expanded`/`aria-controls`.
- **Command bar 56px**: `[collapse] [title/breadcrumb] ····· [allowance pill]`.
- **Allowance pill**: rounded-full, `--secondary/40`, 8px dot (`--primary` <60%, darker amber ≥60%, `--destructive` ≥90%), amount in `--font-display` + label in `--font-label`. e.g. `● $1.23 / $7.00 THIS MONTH`.
- **Mobile ≤767px**: existing Radix sheet, keeping `role="navigation"` + accessible name **"Primary navigation"** (`PortalShell.test.tsx` asserts it).
- **Content**: `mx-auto max-w-5xl (1024px) px-4 py-8 sm:px-6 sm:py-10 lg:px-8`.
- **Nav** — Developer: Home · API keys · Models · Activity · Quickstart (`Resources → Documentation` omitted until a docs site exists). Operator: Overview · People · Providers · Usage · Guardrails.

### 2.5 Component contracts

| Component | Spec |
|---|---|
| Button | `h-9 rounded-md border text-sm font-medium transition-colors`; primary (amber fill + `#0b0e14` text), outline (`--border-strong` + `shadow-xs`), secondary, ghost, destructive (`rgb(217 87 87/.10)` + red text), link. Sizes xs/sm/lg. No hover lift. Pixel face never used for labels >~20 chars. |
| Input / Select | `h-9 rounded-md border --input bg-transparent px-2.5 text-sm shadow-xs`; focus ring; native `<select>` kept. |
| Card / section | `rounded-lg border p-4 bg-card`; headings `14px/500`. |
| Stat strip | One `rounded-lg border` box, `display:grid; gap:1px; background:var(--border)`, `bg-card` cells → 2-col/4-col. Label = Silkscreen 11px uppercase muted; value = **VT323 24px** tabular. Delete the duplicate `.analytics-stat-strip`. |
| Table | Wrapper `overflow-x-auto rounded-lg border`; `thead` = Silkscreen 11px uppercase `--muted-foreground` (verify 4.5:1, else promote), no fill; `th/td px-4 py-3 text-sm`; rows `border-b last:border-b-0 hover:bg-secondary/40`; mono + `truncate max-w-[180px]` for IDs; `tabular-nums`. Wrapper `tabindex="0" role="region"` for keyboard scroll. |
| Status | Dot + text; **text carries meaning**: OK/active/healthy → `--primary`; error/rejected/disabled/revoked → `--destructive-text`; pending/degraded → amber-dark; unknown/info → `--info`. Chip text may use Silkscreen 11px; backgrounds `color-mix(color 14%, --card)`. Never color-only. |
| Toolbar | `h-9 rounded-md` search input + 3 selects — the existing Activity pattern; keep `<label class="sr-only">` + `aria-live` counts. |
| "Jump to" card | `rounded-lg border p-4 hover:bg-muted/60`, Silkscreen kicker, `14px/500` title, 2-line muted desc, chevron. |
| Quickstart step | 24px amber circle badge with a **Silkscreen** numeral + `14px/500` title + muted body + code block. |
| Code block | `bg-secondary/50 rounded-md border`, `pre p-4 pr-12 font-mono text-sm`, ghost copy button top-right, `aria-live` "copied" reset 1.6s; syntax colors limited to the chart series + `--foreground`. |
| Tabs | `bg-muted inline-flex gap-1 rounded-md p-1`; active `bg-background shadow-xs`; `rounded-sm px-3 py-1 text-xs font-medium`. |
| Empty state | `rounded-lg border border-dashed px-6 py-12 text-center` + `14px/500` title + muted body + CTA. |
| Dialog / sheet | Radix, `bg-popover rounded-lg border shadow`, header `border-b`, focus trapped+restored, `Title`/`Description` always. All **five `window.confirm` calls** (`App.tsx:406,418,619,675,926`) become a styled `ConfirmDialog`. |
| Charts | Recharts kept; `--chart-1..5`, grid `--chart-grid`, ticks `--muted-foreground`. Replace `spendSliceColor()`'s golden-angle `hsl()` (`ModelSpendChart.tsx:8-12`) with the fixed series. Keep `isAnimationActive={false}` + sr-only tables. |

## 3. Page-by-page plan

| Route / file | Target layout (reference pattern) |
|---|---|
| `/auth/login` · `AuthPage.tsx` | Centered card on `--background`, brand mark, Sign in / Create account tabs, amber primary, inline error. No rail. |
| `/developer` · `App.tsx:281` | "Hey, {name}" h1 + muted line → **4-up stat strip** (Requests / Total tokens / Prompt tokens / Completion tokens, VT323 values) → **Jump to** 3 cards → **Quickstart** 4 numbered cards with copyable curl → allowance runway (stepped bar) + recent activity + top-models table. |
| `/developer/keys` · `App.tsx:398` | Header + primary action → table (label, mono prefix, models, spend cap + stepped bar, RPM, last used, status, actions). Create/Edit dialogs; one-time secret in a mono `secret-field` with copy + "you won't see this again". |
| `/developer/models` · `ModelCatalogPage.tsx` | Search + capability chips → 1/2/3-col card grid; card = provider 12px muted, name `14px/500`, `line-clamp-2` desc, mono copyable ID, price line. Filters stay in the URL. |
| `/developer/models/*` · `ModelDetailPage.tsx` | `← All models` → chips + mono ID copy → h1 + 62ch desc → **4-up facts strip** (context / input price / output price / max output, values VT323) → collapsible **Technical details** → **Code examples** with cURL/JS/Python tabs + copy. |
| `/developer/activity` · `DeveloperActivityPage.tsx` | Search + `All results` / keys / models filters → `Time · Model · Tokens · Cost · Result`, amber `OK` + mono latency; cursor "Load more". **P2 optional:** row opens a right sheet (request ID, key, latency, token split, cost source). |
| `/developer/quickstart` · `App.tsx:590` | Amber/Silkscreen numbered steps, code blocks, "What gets tracked / Usage truth" asides. |
| `/operator` · `App.tsx:597` | Stat strip → spend runway (stepped) → provider health → recent activity → analytics → top models. |
| `/operator/people` · `App.tsx:607` | Search + invite → table (name, email, status, allowance stepped runway, RPM, keys, requests, last active) + invite + allowance dialogs. |
| `/operator/providers` · `ProviderListPage.tsx` | Brand-grouped collapsible sections → connection rows (health dot, mono host, discovered/approved counts, budget runway) → `OfferDetailSheet` with price review, route priority, availability. |
| `/operator/usage` · `OperatorUsagePage.tsx` | Same toolbar/table treatment, 10 columns, cursor paging, internal scroll (watch 1024–1280px). |
| `/operator/guardrails` · `App.tsx:883` | Two-column form cards (cap + reserve, blocked IPs, global stop as destructive) + audit log. |
| `*` · `App.tsx:974` | Dashed empty-state 404. |
| ~~`/dashboard`~~ | **Deleted in Task 1.** |

## 4. Legacy Control Room removal (Task 1 detail)

Evidence: `app/static/app.js` is the **only** non-test caller of `X-Admin-Token` / `/api/admin/*` / `/api/dashboard`. The React portal, `app/cli.py` and `app/scanner.py` never touch them.

**Delete**
1. `app/static/` (index.html, app.js, style.css) — the directory itself.
2. `app/main.py`: `:14` + `:53` (`/static` mount), `:454-456` (`GET /dashboard`), `:486-718` (`/api/dashboard` + all `/api/admin/*`), `:423-425` (`require_admin`). Keep `/assets` mount (`:54`) and `/v1` (`:721+`).
3. `app/main.py:466-470`: drop the `/dashboard` redirect — `/` returns `portal_index()` unconditionally (missing build already raises 503 `portal_frontend_not_built`).
4. `app/config.py`: `:23` field, `:68-69` bootstrap generation, `:80` `runtime-secrets.json` key. Keep `provider_secret_key` / `provider_key_pepper` and the file itself.
5. `.env:6` `ADMIN_TOKEN=`; prune `admin_token` from the live `runtime-secrets.json`.
6. Tests: delete `tests/test_provider.py:65-74` (dashboard page/static/admin-token tests); rework the ~15 admin-seeded tests (`:17-53,76-147,160-170,199-233`) to seed through `Database` directly (keep their `/v1` assertions — budget, rate limit, spend cap must still be covered); drop the `admin_token` assertion at `:240-249`.
7. Docs: `README.md:18,20,76-81`; `PLAN.md:58,387`; `deploy/README.md:9,37,39` (rollback checks → `/`, `/v1`, portal login); `security_best_practices_report.md:11,29`. Historical plans/design files stay as records.

**Do NOT touch:** `app/database.py` tables/methods, `app/portal_db.py` migrations, `app/portal_api.py` guardrails/blocked-ips, `/v1` IP-block/budget logic.

| Legacy asset | Verdict | Why |
|---|---|---|
| `blocked_ips` | keep | shared with portal guardrails (`portal_api.py:1089,1136,1150`) and enforced in `/v1` (`main.py:724,738`) |
| `provider_api_keys` | keep | still-valid `/v1` credentials (`main.py:95-99`) |
| `usage_records` | keep | feeds portal analytics + budgets |
| `upstream_profiles` | keep | portal connections bind `legacy_profile_id` |
| `budget_reservations` | keep | summed into portal global budget |
| `/api/dashboard`, `/api/admin/*`, `admin_token` | **delete** | used only by the deleted `app.js`; portal equivalents exist |

**Verify:** `pytest tests/` green · `GET /` → portal · `/dashboard` → 404 · `/api/admin/keys` → 404 · `/v1/models` with a legacy key → 200 · `/api/operator/guardrails` still lists blocked IPs.

## 5. Accessibility acceptance criteria (WCAG 2.2 AA)

**P0:** all text pairs ≥4.5:1 with the corrected tokens; control borders ≥3:1 (`--border-strong`); visible `:focus-visible` everywhere incl. amber buttons; skip link first tab stop; tables have labels + `scope="col"`; no click-only rows; dialogs have Title/Description, trap and restore focus; inputs labeled; copy actions announce; loading/empty/error announced; `aria-current="page"` on active nav; **Silkscreen 11px labels verified ≥4.5:1 or promoted in color**; **VT323 used only ≥18px**; progress bars expose `role="progressbar"` + values with visible numeric text.

**P1:** sidebar roving focus + `aria-expanded` collapse (persisted); status by text+shape not hue; `prefers-reduced-motion` neutralizes shell/dialog motion; `scroll-margin-top` clears the bar; ≥44px targets at all widths; mobile sheet labeled and escapable.

**P2:** keyboard-scrollable table regions; 320px + 400% zoom reflow; axe/Lighthouse zero critical/serious; NVDA + VoiceOver smoke of shell, one dialog, one table, one chart.

## 6. Implementation strategy

`styles.css` is **three stacked layers** (L1 `:7-232`, L2 `:234-439`, L3 `:441-500`) with **106 duplicated selectors** where the later layer silently wins; `App.tsx` is a 976-line monolith with 5 dead exported components (`OperatorUsagePage:873`, `ActivityFilters:576`, `PersonPolicyDialog:694`, `ProviderCreateDialog:781`, `ModelPolicyRow:820`) and 3 duplicate runway/usage implementations. This is a re-shell, not a reskin.

**Order (never render unstyled):**
1. Legacy dashboard removal (backend, independent of visuals).
2. Prune dead code + 15 dead CSS selectors + 3 unused tokens; resolve the 8 JSX classes with no CSS rule.
3. **Append** the new `:root` at the *end* of `styles.css` (later declarations win; a top-level `@import` would lose), verify, then delete the old token block, `:10/:11` literals and the 50 rogue hexes.
4. Fonts: remove the 5 IBM Plex `@import`s → Noto Sans + Maple Mono + VT323 + Silkscreen; define `--font-*`; set the scale; add `tabular-nums`.
5. Geometry/motion/breakpoint pass, isolated from color.
6. Shell extraction into `src/ui/shell/{AppShell,Sidebar,TopBar,AllowancePill,nav}.tsx` + `PortalShell.test.tsx`.
7. Primitives (incl. status amber, stepped runway, `ConfirmDialog`).
8. Pages: developer → operator → auth/404.
9. Split `styles.css` into `tokens.css` + `components.css`, merge L1/L2/L3 duplicates into one rule per selector.
10. Finish: build, screenshots, detector, review, rewrite DESIGN.md from the built world.

### Task breakdown + verification

| # | Task | Key files | Verify |
|---|---|---|---|
| 0 | Rewrite design authority (Ayu + retro layer), supersede banners | `.ulpi/design/DESIGN.md`, `hackclub-ai-portal-refresh.md`, `poorup-console-refresh.md`, `2026-09-28-poorup-console-ui-refresh.md`, `.impeccable/surfaces/frontend-src-ui-app-tsx.md` | docs review |
| 1 | **Delete legacy Control Room** (§4) | `app/static/`, `app/main.py`, `app/config.py`, `.env`, `runtime-secrets.json`, `tests/test_provider.py`, README/PLAN/deploy docs | `pytest tests/` + the five HTTP checks in §4 |
| 2 | Dead-code + CSS-layer prune | `App.tsx`, `styles.css` | `npm run typecheck && npm run lint && npm run test` |
| 3 | Tokens + hex migration | `frontend/package.json`, `styles.css` | same + `?preview=developer` |
| 4 | Fonts (4 faces) + type scale + radius/motion/breakpoints | `styles.css`, `index.html` (`theme-color` → `#0b0e14`) | same |
| 5 | Shell: rail + command bar + pill | new `src/ui/shell/*`, `App.tsx`, `PortalShell.test.tsx` | tests + preview both roles |
| 6 | Primitives + stepped runway + `ConfirmDialog` | `styles.css`, `App.tsx`, `AllowanceSummary.tsx`, `MoneyRunway.tsx` | tests |
| 7 | Developer pages | `App.tsx`, `developer/*` | DeveloperTask9, ModelCatalog/Detail, AnalyticsRange |
| 8 | Operator pages + charts | `App.tsx`, `operator/*`, `charts/*` | ProviderTask8, UsageCharts |
| 9 | Auth, session screens, 404 | `AuthPage.tsx`, `App.tsx` | AuthPage, PrecisionAndShellEscaping |
| 10 | A11y P0/P1 + responsive | all UI | §5 checklist + 320px/400% zoom |
| 11 | Finish: build, screenshots, `impeccable detect`, finish review, documenter | `frontend/dist`, `.impeccable/review/*` | `npm run build` + detector + review |

Per-task commands: `cd frontend && npm run typecheck && npm run lint && npm run test`; Task 1 additionally `pytest tests/`. Visual check via `npm run dev` + `?preview=developer|operator` (there is still **no Vite proxy** — real data only appears behind FastAPI).

## 7. Risks and open decisions

| Risk / decision | Handling |
|---|---|
| VT323 low x-height; Silkscreen caps-only feel | Hard rules: VT323 ≥18px only, Silkscreen 11–12px uppercase only; both verified at Task 4 with a rendered sample before pages are touched |
| Silkscreen 11px contrast in muted color | Check at Task 4; promote to `--foreground`/`--primary` if <4.5:1 |
| Amber = both action and "OK" (reference-faithful) | Accepted; green reserved for "available/approved" chips |
| Tests assert current markup | Update `PortalShell`/`AuthPage` tests in the same task; keep `role="navigation"` + "Primary navigation" |
| Admin-seeded `/v1` tests lose their setup path | Re-seed via `Database` directly — assertions on budget/rate-limit/spend-cap behavior must survive |
| 1280px → 1024px content narrowing crowds the 10-column operator usage table | Internal horizontal scroll; check 1024–1280 explicitly |
| `admin_token` removal from a live `runtime-secrets.json` | Manual deploy step: edit the file on the host (never regenerate it — deploy README) |
| Docs link in sidebar `Resources` | Omit until a docs site exists; optionally point at `/developer/quickstart` |
| `Europe/Berlin` + `en-GB` hard-coded in components | Centralize into `src/lib/format.ts` at Task 7 (behavior-preserving) |
| Node ≥20.19 (Vite 7) on the deploy host | Build `frontend/dist` locally/CI and transfer, as the deploy README already instructs |
| Retro creeping past its budget | The rejected-cue list in §2.3 is binding; any addition is a new decision, not a polish step |

## 8. Explicitly out of scope

`/v1`, auth/session/CSRF, budgets, routing, model approval · Tailwind/shadcn · new UI/icon libraries (Lucide stays, 16px/1.5 stroke) · light mode + toggle · public landing page · scanline/notch/square-icon cues · deployment/cutover · commit/push without explicit request.

## 9. As-built notes (2026-09-28 implementation)

- `--quiet-foreground` corrected `#6c7380` → `#7a818d` (the reference value failed AA at 11px); `--secondary: #131721` added (was missing from the CSS token block).
- Collapse toggle uses `aria-pressed` (not `aria-expanded` + `aria-controls`): the rail is never hidden, only narrowed.
- Operator pill formats with number-safe `money()` instead of `formatUsd(String(...))` (avoids exponent-form strings).
- Preview workspace switcher exists in the command bar (desktop) and the nav sheet (mobile); labels differ so only one "Choose portal" is ever in the tree.
- `ConfirmDialog` blocks Escape/outside-pointer dismissal and disables Cancel while `busy`; the global-stop confirm has its own `stopBusy` flag.
- Review verdict applied: over-cap red fill deferred (runway clamps at 100% by `ratioPercent`; the pill dot already signals ≥60/90% exposure). Direct-`db` provider tests accepted as the price of deleting the admin HTTP surface.
- Detector (`impeccable detect`) clean on all touched UI targets; typecheck/lint/vitest (83) + pytest (247) green at ship.
