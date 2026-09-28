---
project: Sponsored Provider
design_system: Radix UI + existing React/Vite components themed with .ulpi/design/DESIGN.md
platform: Responsive web, one same-origin application
---

# Operator and Developer Portals

## Design read

One sponsored AI gateway has two audiences: the operator protects a shared upstream allowance; developers need their own keys and a clear view of their own usage. The interface makes that boundary visible on every page.

Every screen must read as the same product if placed side by side.

Design direction: technical/utilitarian, inherited and refined from the existing Sponsored Provider identity. DFII: impact 4 + context fit 5 + feasibility 4 + performance safety 4 - consistency risk 2 = 15. The existing usage runway remains the signature.

## Product boundary

- The operator owns provider connections, model approval/pricing, invitations, user allowances, global stop controls, and account-wide reporting.
- A developer signs in, creates API keys, selects from the approved unified catalog, and sees only their own keys and request history.
- Developers never enter or receive upstream provider credentials. They call the stable OpenAI-compatible `/v1` endpoint using a one-time-revealed sponsored key.
- The initial provider contract is OpenAI-compatible model discovery (`GET /models`) and chat completions, including streaming only when supported by the selected upstream.

## Navigation

### Operator portal

1. Overview
2. People & keys
3. Models & providers
4. Usage
5. Guardrails & audit

Provider profile details, pricing, invitations, and settings are contextual sub-pages or drawers, not extra top-level navigation.

### Developer portal

1. Home
2. API keys
3. Models
4. Activity
5. Quickstart

The signed-in account menu contains identity, session, and sign-out actions. Operator access is a role, not a separate weakly protected admin token field in browser storage.

## Screen specifications

### Sign-in and access states

- Sign-in uses local usernames and passwords with secure same-origin session cookies (Hack Club Auth is dormant). Accounts are identified by the portal user record, not mutable email.
- Day-one eligibility is Hack Club Auth sign-in plus a valid operator-issued invite. Do not require a separate verification-status scope in the first release.
- A valid identity without an invitation sees a pending/access-needed state, never a partially provisioned API key.
- Disabled users lose portal and issued-key access promptly. The operator can see who invited/approved them and when.
- Session expired: preserve the requested return path, show a plain re-authentication prompt, and do not discard saved form drafts that contain no secrets.

### Developer Home

Purpose: answer “what have I used, what remains, and what should I do next?”

- Summary strip: requests, successful/error requests, input/output/total tokens, estimated spend, and allowance remaining for the selected time range.
- Usage trend: request, token, or spend series with explicit period and units.
- Recent Activity preview: last few request rows and a link to Activity.
- Key status: active/disabled, model policy, per-key cap, and nearest reset time.
- Empty state: explain how to create a key and make the first OpenAI-compatible call.

### Developer API Keys

Use a searchable table on desktop and stacked key rows on mobile. Show label, masked prefix, model policy, spend used/cap, period reset, RPM, created/last-used, and state.

Key creation flow:

1. Enter a descriptive label.
2. Model access defaults to `All approved models`; switching to `Selected models` opens a searchable multi-select grouped by provider and capability.
3. Optionally set a per-key spending cap and reset period. It can only be equal to or tighter than the user's operator-assigned daily/weekly allowance. The user allowance is assigned by the operator and aggregates every key owned by that user.
4. Create the key atomically with the selected policy; reveal the secret once with Copy and integration snippets.
5. The list shows only the prefix thereafter. Rotate/revoke disables the old secret; archive preserves history.

Selected model policies are fixed to their approved IDs. `All approved models` is dynamic: newly synced models remain unavailable until an operator approves them and configures a usable price, then all-model keys inherit them. Restricted keys do not inherit additions.

### Developer Models

- Catalog is filtered to operator-approved models only.
- Each row shows canonical model ID, provider label, supported capability (text/vision), input/output price per million tokens, and last catalog sync.
- Search, provider filter, and capability filter are visible above a paginated/virtualized list.
- Unpriced, stale, or unhealthy models have explicit states. They cannot be selected for a new key until the operator resolves policy/pricing.
- Copy model ID and a minimal request example. Never show the upstream base URL or secret.

### Developer Activity

Recent requests table, newest first:

| Column | Meaning |
|---|---|
| Time | Timestamp in the user's locale, with exact time on hover/focus |
| Model | Canonical requested model ID |
| Tokens | Input / output; total available in row detail |
| Cost | Local estimate with an `Estimated` label, or provider-reported only if actually reconciled |
| Result | Success/error plus latency |

Filters: time window, model, key, and result. Use cursor pagination / `Load more`, not infinite unbounded scrolling. Row detail shows request ID, provider, key label, that user's request source IP, token breakdown, cached-token count if supplied, and safe error category. It never exposes prompt/response, upstream credentials, or another user's IP. The operator's Usage view may include client IP for abuse investigation.

Zero-token, free, unknown-price, streaming-without-usage, and failed calls each have distinct display states; a missing upstream usage field must not be rendered as a confirmed `Free` request.

### Operator Overview

- Headline measures: requests, success rate, total input/output tokens, local estimated cost, remaining global stop, and p95 latency for a selectable period.
- One time-series panel switches between requests/tokens/spend and labels units.
- Model/user ranking and recent errors support drilldown to Usage.
- Provider health and last model sync show freshness explicitly.
- The global budget runway is the signature element. The cap, reserved amount, accounted amount, safety reserve, and stop state have separate labels.
- Billing reconciliation is separate from local estimate. It shows provider, source, amount, observed time, and adjustment history; never silently rewrites request history.

### Operator People & Keys

- Searchable people table: identity, status, assigned daily/weekly allowance, aggregate use across their keys, request volume, last active, and action menu.
- Person detail: owned keys, activity summary, allowance/RPM policy, invite/approval state, and disable action.
- Key detail: owner, masked prefix, selected/all-approved model policy, cap/reset, RPM, use and history. Secret material is never retrievable.
- Disable/revoke blocks new requests immediately. Archive hides a key from the default active list but retains it and all usage history. There is no hard-delete control in the UI.

### Operator Models & Providers

Provider setup dialog: display name, compatible base URL, API key (write-only), and optional endpoint notes. After save, operator action `Test & sync` performs a credential-safe `/models` probe. The results show fetched count, last successful sync, health, and catalog differences. Providers are not active for users until the operator approves models and configures pricing.

Pricing is per provider/model and records source, currency, input/output rates, optional cache rate, effective date, and verification state. An unpriced model fails closed. Existing request rows preserve the rate snapshot used at request time.

### Operator Guardrails & Audit

- Global provider hard stop and safety reserve.
- User aggregate allowance (daily/weekly) and user-wide RPM; optional per-key caps/RPM can only tighten these.
- Model/provider allowlists, emergency stop, abuse IP block, and rate-limit errors.
- Audit records actor, action, target, timestamp, and redacted before/after policy values. Never record raw secrets.

## Usage and budget semantics

- A request event is owned by both `user_id` and `api_key_id`; the provider and model are stored as stable IDs/snapshots.
- Capture request count, result, latency, input/output/total tokens, cached tokens when upstream reports them, IP for operator abuse review, and local estimated cost.
- Prompts and completions are not persisted.
- Cost estimate uses the configured model price snapshot. If cache usage is not reported, use the configured conservative input rate and label the result estimated.
- Effective spend limit is the minimum of global hard stop, the user's period allowance, and optional key-period cap. Reservations happen before upstream forwarding to protect concurrent requests.
- Effective RPM applies to the user across all their keys, with an optional lower per-key limit and an operator-controlled upstream safety ceiling.
- The operator assigns the user-wide RPM. A developer may choose a lower per-key RPM but cannot raise either the user or upstream ceiling.
- Period reset timezone is explicitly shown. Default is UTC.

## Core user flows

### Join and activate

Hack Club OIDC sign-in → validate invitation/approval → create or load local user → provision session → Developer Home. Cancelled login, invalid/expired invite, suspended identity, and expired session have clear recovery states.

### Create and use a key

Developer Home/API Keys → Create → choose all-approved or selected models → choose optional tighter cap/reset → server validates against user policy and writes key+policy in one transaction → show secret once → user copies endpoint/snippet → first activity appears when a request is accepted.

### Add provider and publish models

Operator Models & Providers → Add profile → save encrypted secret → Test & sync → inspect catalog results → set/verify price → approve selected models → approved models become available to all-model user keys and selectable for restricted policies.

### Respond to spend spike

Operator Overview alert → Usage filtered by user/model/key → inspect request counts/tokens/status/latency → disable/archive affected key or user, block model/IP, or lower policy → audit trail records the action.

## Component and interaction rules

- Use Radix/shadcn primitives for dialog, select/combobox, tabs, tooltip, dropdown, and accessible table controls. Theme only with locked tokens; do not create a second component vocabulary.
- Charts use accessible labels and a text/table alternative; do not make color the sole indicator.
- Every async surface supports loading, empty, stale, partial, success, and error states. Sync actions are idempotent and show last updated time.
- Destructive/high-impact actions (disable user, revoke key, global stop) require clear contextual confirmation; routine edits save with inline result feedback.
- Desktop sidebar is role-specific. Mobile uses five-item maximum bottom navigation plus `More`; all actions have at least 44px touch targets and safe-area padding.
- Keyboard: complete portal navigation without pointer; dialogs trap/restore focus; tables and comboboxes announce labels and state; respect reduced motion.

## Core component contracts

| Component | Purpose and primary state | Interaction and accessibility |
|---|---|---|
| Usage runway | Show operator-global or developer-personal used/remaining budget, period and reset time | Text values and accessible progressbar; warning/stop labels never color-only; collapsed mobile state retains the numeric summary |
| Usage metric strip | Requests, input/output/total tokens, local estimated spend and p95 latency for the selected range | Each metric has unit and tooltip definition; skeleton, no-usage, partial-data and stale states |
| Activity table | Paginated request history with time/model/token split/cost/result/latency | Sort/filter with URL-backed state; row expansion by keyboard; empty/error/retry states; no prompt body |
| Model picker | Search approved catalog and choose all-approved or a fixed model set | Accessible combobox/listbox; keyboard arrows/space/enter/escape; provider/capability labels; stale/unpriced items disabled with reason |
| Create-key dialog | Create one user-owned key with models, tighter optional spend period and optional tighter RPM | Validate against server-returned remaining allowance; prevent double submit; reveal secret once; copy confirmation and safe close warning |
| Provider connect dialog | Store an upstream name/base URL/secret and test model sync | Secret input is write-only; sync state/progress/error; no returned secret in response or browser storage |
| Limit editor | Operator sets user/global ceilings; user can only set stricter key overrides | Show inherited/effective value and reset period; inline validation; server remains authoritative |
| Confirm action dialog | Disable/revoke/archive user/key, block model/IP, or emergency stop | Name target and consequence; focus trap; explicit cancel; success toast plus audit entry |

All dialogs, toasts, charts, and tables use the same tokens and Lucide icon set. Avoid nested cards; use dividers and tables where they improve scan speed.

## Non-goals for initial release

- Public self-registration without invitation/approval.
- Payments, user wallet deposits, resale or billing users beyond the operator-assigned allowance.
- Marketplace reviews/rankings, public model comparison benchmarks, prompt storage, playground chat history, files/RAG, tools/plugins, automatic cross-provider fallback, native Anthropic/Google protocols, or automatic import of Alibaba account billing credentials.

## Acceptance criteria

- Operator and developer portals share the same-origin app but enforce separate roles server-side.
- A developer cannot read/change another user's keys, activity, usage, or limits by changing URL/query IDs.
- New user keys are created with final policy atomically and shown in plaintext once.
- Keys/models/users can be revoked/archived without removing request history.
- New upstream models stay unavailable until enabled and priced; no price means request rejected before upstream call.
- Global, user, and per-key spend/RPM limits are independently observable and cannot be bypassed by creating another key.
- API `/v1` path and OpenAI-compatible request/response contract remain backward compatible.
- Mobile portal, keyboard flow, empty/error/loading/stale states, and user data isolation are verified before opening the invite pilot.

## Design preflight (spec review)

- Identity: passes at specification level. All screens bind to one palette, type pair, spacing/radius scale, Lucide icon family, and technical voice.
- Anti-slop: passes at specification level. No marketplace clone, purple glow, nested-card wall, fake trust claims, or decorative metrics; the shared/personal usage runway is the brief-specific signature.
- State coverage: specified for auth, sync, model discovery, key creation, activity, limits, and provider errors. Implementation must exercise every state.
- Accessibility: keyboard paths, touch sizing, semantic status labels, reduced motion, and contrast are normative. Verify rendered ratios/focus against tokens in implementation.
- Layout: sidebar shell, KPI/stat strip, chart/data region, and table-first Activity form distinct page patterns without changing product identity.
- Cognitive load: five destinations max per role; advanced provider pricing stays in operator detail views.
- Self-critique (design spec only): distinctiveness 3/4; hierarchy 3/4; consistency 4/4; accessibility 3/4; state coverage 4/4; copy 4/4; restraint 4/4; motion 3/4. Total 28/32. Visual scores remain provisional until built screens are rendered and reviewed.

## Build handoff

Implement this spec in the existing repository as a single FastAPI deployable serving a React/Vite static SPA. Keep `/v1` as the stable gateway contract. Use the existing technical/utilitarian identity in `.ulpi/design/DESIGN.md`; theme Radix/shadcn with the locked tokens. Do not deploy or replace the Nest service until migration and rollback are reviewed.
