---
project: Sponsored Provider
design_system: Radix UI + shadcn/ui themed with .ulpi/design/DESIGN.md
platform: Responsive web, same-origin operator and developer portals
---

# Provider Catalog and Credits UI

## Design read

The operator needs a calm control room for a set of upstream connections; developers need a straightforward view of their own expiring allowance and model access. Extend the existing technical/utilitarian identity rather than making a second visual product.

## Locked design binding

- Read `.ulpi/design/DESIGN.md` first. No new palette, font, radius, spacing, icon, or motion system is introduced here.
- Keep the existing “usage runway” signature: show a shared provider-connection cap beside the separate user credit allowance without implying they are the same balance.
- Preserve five-or-fewer top-level destinations per role, dense operator tables, user-focused summaries, responsive mobile controls, no page-wide horizontal scrolling, and no prompt/response history.
- Use semantic labels for price source, freshness, approval, availability, and route status; color is never the only signal.

## User journeys

### Sign up with a local account

1. The unauthenticated visitor opens a local username/password sign-in form; no Hack Club Auth control is shown.
2. An invited visitor follows an invite link and sees the remaining uses/expiry state without seeing inviter-only data.
3. Signup accepts username/password and the invite token; account creation and invite-use consumption happen atomically.
4. A new developer receives one single-use invite to share. They can view/copy it once and see whether it remains unused or has been consumed; they cannot mint replacements.
5. Invitation tokens live in the URL fragment rather than query parameters; signup sends the token in a POST body and removes the fragment after success.

### Operator: connect and discover a provider

1. From Providers, choose **Add connection**.
2. Enter provider brand, private label, OpenAI-compatible base URL, and credential. Explain credential secrecy at the field and confirmation step.
3. Choose **Test & fetch models**. Show distinct testing and discovery phases so users know whether auth or model import failed.
4. Display the discovered count and grouped results: matched to Models.dev, ambiguous match, missing price, changed price, and already known.
5. Review prices and capabilities; approve pricing; separately switch offers on for users.
6. Success returns to provider detail with last-sync time, health, connection cap, and offer count.

### Operator: issue invitations

1. In People, choose the maximum number of accounts for one invite link and its expiry.
2. The operator sees used/max, expiry, and revocation state; the raw link is shown once and can be copied.
3. Revoking an invite prevents any further signup; already created accounts are unaffected.

### Operator: merge and route duplicate models

1. Provider detail groups same-brand/same-canonical-model connections under one catalog offer.
2. Open an offer to see public model ID, display label, active approved rates, price source/time, and all matching connections with raw upstream IDs.
3. Select a primary connection and drag/keyboard-order eligible fallbacks. Each route shows health, last seen, and price match.
4. A rate mismatch blocks fallback and explains both rates and the required action. An offer-level availability switch controls developer exposure; a separate route switch controls only that connection.
5. Save confirms the effective routing change and writes an audit event.

### Developer: create a key and inspect allowance

1. Home displays allowance remaining, expiry/reset time in Europe/Berlin, request/token totals, estimated spend, and recent activity.
2. Models lists only published offers as `Provider / Model`, with effective input/output USD prices and capability labels.
3. Key creation defaults to all enabled offers. An optional searchable multi-select pins a subset; optional spend/RPM controls can only reduce access.
4. Key secret is revealed once; subsequent views show only label/prefix. User can copy OpenAI-compatible base URL and snippets.
5. Activity shows only this user’s request facts. Request detail never contains prompt or completion.

## Operator navigation and screens

### Providers (primary)

Brand list contains expandable connection rows. Summary fields: brand/private label, health, last successful sync, discovered/published offer counts, spend used/cap, reset, and active reservations/headroom. Primary action is **Add connection**.

Connection detail has two clear areas:

- **Connection settings:** base URL display (secret-free), credential state (configured/rotate), test, sync now, enable/disable, spend amount, period, reserve, current usage/headroom.
- **Model offers:** table grouped by canonical provider/model, with public ID, display label, rates, price source/status, capability, offer availability, and route count.

### Offer detail

Use a right-side sheet on wide layouts and full-screen dialog on phones. Sections: identity and user-facing ID; pricing (active and pending side by side); match evidence; capability claims; offer availability; ordered routes; recent usage. Keep irreversible actions separated and confirmed.

### Developer model detail

Use a focused detail page reached from a compact searchable provider-grouped catalog. Lead with `Provider / Model` and the stable API ID, then show input and output USD per 1M tokens in a paired rate strip. Include cached-input price, context window, max output, modalities, and code examples only when verified. Label the price source and freshness; omit unknown metadata rather than displaying guessed values. Code examples use the public model ID and same-origin OpenAI-compatible endpoint.

### Usage / safeguards

Reuse the existing activity table and filters; add provider brand, connection, estimate/reported source, and route. Show spend estimates and external invoice snapshots as separate values. Usage rows link to stable offer/connection snapshots, not only current records.

## Developer portal changes

- Home allowance card clearly says **your shared allowance**, amount remaining/total, daily/weekly period, reset time, and that unused credits expire.
- Model catalog supports search, provider filter, capability filter, and price sort. Each offer’s display name includes provider; prices show input/output per million USD, not one blended rate.
- API key form: all enabled offers by default; selected-model mode searchable and grouped by provider. State that per-key cap is a stricter sub-limit and does not add credits.
- Activity table: time, provider/model, input/output/cached tokens, estimated charge, latency, status, and request ID. Unknown token usage renders “Not reported”; cost is labeled estimated or provider-reported. On mobile, cards expose the same fields without horizontal page scrolling.
- Account/invite area: one single-use invite per developer, with available/used status and a one-time copy of the raw invite link; no HCA sign-in or account link appears.

## Component briefs

### Local sign-in and invite signup

- Purpose: authenticate a user with a local account and prove an invite is valid before signup.
- Fields: username, password, and invite token carried from the link; password manager autocomplete is supported.
- States: generic invalid-credentials error, invalid/expired/revoked/exhausted invite, rate limited, loading, and session expired.
- Accessibility: visible labels, password visibility control with accessible state, keyboard submission, errors connected to fields, and no auth-by-color or icon-only affordance.

### Provider connection row

- Purpose: distinguish provider brand from a concrete credential/base URL connection.
- States: healthy, test needed, sync stale, failed, paused, budget near cap, cap stopped.
- Actions: open, test, sync, pause/resume. Secret is never rendered.
- Responsive: brand summary row plus expandable connection detail on mobile.
- Accessibility: button names include brand + private label; status announced as text; actions keyboard reachable.

### Model offer row

- Purpose: manage a single provider-scoped public model despite multiple same-provider routes.
- Fields: public ID, display label, input/output rate, price source/effective time, published state, route count/health.
- States: discovered, match needed, price needed, pending approval, priced/off, published, stale, route mismatch.
- Accessibility: sortable table headers with `aria-sort`; state/action labels do not rely on color.

### Price review panel

- Purpose: compare active rate, Models.dev suggestion, and optional provider-reported rate before publishing.
- Behavior: changed suggestion is pending; operator can accept, edit USD rates, or reject. Approval records source, actor, and time.
- Validation: nonnegative decimal-safe USD per million input/output; optional cache rate; do not accept NaN, infinity, or silent zero defaults.
- Accessibility: each field has unit and source in its accessible name; errors linked with `aria-describedby`; focus moves to the first invalid field.

### Route priority editor

- Purpose: choose primary and ordered same-brand fallbacks.
- Behavior: route can be added only if exact model mapping is confirmed, route is enabled/healthy enough, and effective user rate matches. Reorder by buttons and keyboard; drag is an enhancement only.
- Confirmation: before saving, summarize primary, fallbacks, and price equality. Warn if routing changes future provider spend exposure.
- Accessibility: ordered list semantics, accessible “Move up/down” actions, announced priority changes.

### Allowance and cap runway

- Purpose: show different financial scopes without conflating them.
- Operator view: provider connection exposure/cap/reserve and selected user allowance each use separate labeled runways.
- Developer view: own allowance remaining/reset and optional key sub-cap.
- Never imply upstream invoice precision. Include active reservations in “reserved” rather than spent.

## State and error coverage

| State | UX |
|---|---|
| No connections | Explain OpenAI-compatible URL + credential; CTA Add connection. |
| Testing | Step progress: validating URL, authenticating, fetching models; allow cancel before persistence. |
| Partial model match | Keep matched rows actionable; ambiguous rows are individually reviewable; do not block the entire provider. |
| No price match | Show “Price required”; offer manual USD entry; model stays hidden from developer catalog. |
| Sync failure | Retain last known catalog; show error category/time and retry; no blank overwrite. |
| Stale route | Mark last seen and exclude from new route use pending successful sync/review. |
| Price update | Active and suggested versions side-by-side; no silent save. |
| Budget low/stopped | Show cap, used, reserved, reserve, reset; explain new-request behavior. |
| Empty developer catalog | Explain operator approval/availability requirement; don’t show fake models. |
| Insufficient allowance | OpenAI-compatible structured rejection; portal shows remaining allowance/reset and request ID, no secrets. |
| No usage report | Preserve unknown token fields and show estimated cost basis. |
| Session expiry/offline | Preserve nonsensitive draft, never persist raw provider secret in browser storage, re-authenticate/retry clearly. |

## Responsive and accessible behavior

- Desktop: persistent role-specific sidebar; wide offer/connection tables with sticky headings and filters.
- Tablet: compact navigation and table columns prioritizing model, price, availability, and route health.
- Phone: bottom navigation/More sheet; provider connection cards; offer detail as full-screen dialog; route priority moved with labeled controls; cap runway and reset visible near top; 44px minimum touch targets and safe-area spacing.
- Tables may scroll within their own container, but the page itself has no horizontal overflow. Use native touch scroll and avoid always-visible decorative scrollbars.
- Full keyboard path for dialogs, searchable comboboxes, data tables, switches, filters, and route reordering. Return focus to opener on close.
- Live region announces sync completion, price approval, offer publish/disable, route reordering, and budget stop. Respect reduced-motion setting from locked system.
- Keep WCAG AA contrast values from `.ulpi/design/DESIGN.md`; semantic color always has text/icon.

## Visual identity and anti-slop gate

- Direction remains **technical / utilitarian**, not a new theme. The counterfactual test passes because the distinctive usage runway connects provider exposure to personal allowance while explicitly showing they are separate controls.
- Keep Radix UI + shadcn/ui primitives themed with existing tokens; use IBM Plex Sans/Mono, Lucide, accent sparingly, and compact purposeful tables.
- Explicitly avoid: generic three-card dashboard grids, arbitrary gradients/glows, invented provider health numbers, unexplained green “free” states, nested cards, icon-only destructive controls, confetti, and fake precision.
- Do not clone OpenRouter. Borrow only provider-aware catalog grouping and readable usage detail; retain the existing Sponsored Provider identity.

## Pre-flight self-check

- Identity consistency: pass; all values inherit locked `.ulpi/design/DESIGN.md`.
- Flow states: pass; discovery, partial matching, price review, stale/failure, cap stop, and user-empty states are specified.
- Accessibility: pass at spec level; keyboard, screen-reader, contrast, touch, and reduced-motion criteria are listed for implementation QA.
- Cognitive load: pass; retain five-or-fewer top-level nav destinations, use provider/model progressive disclosure, and limit the connection form to short steps.
- Distinctiveness: pass at spec level; no new visual identity, signature is the two-scope usage runway.
- Layout craft: pass at spec level; the proposed screens use dashboard/runway, dense table, staged form, and detail-sheet layout families.
- Remaining visual verification: implementation must test real mobile/desktop layouts and evaluate actual data density; this document is not proof of rendered UI quality.

### Scored self-critique

| Axis | Score (0–4) | Rationale |
|---|---:|---|
| Distinctiveness | 3 | The provider/user usage runway is specific to the two independent budget scopes. |
| Hierarchy and focus | 3 | Provider detail groups sync, price, offer, and route controls; responsive implementation still needs validation. |
| Consistency | 4 | The existing locked identity is explicitly retained. |
| Accessibility | 3 | Keyboard, announcement, contrast, and touch criteria are specified; implementation testing remains. |
| State and edge coverage | 4 | Sync, pricing, routing, budget, authentication, and no-data states are included. |
| Copy quality | 3 | Labels distinguish source, estimate, approval, and availability; final UI copy review remains. |
| Restraint | 4 | No new visual tokens or ornamental dashboard widgets are introduced. |
| Motion motivation | 3 | Motion inherits existing restrained tokens and reduced-motion behavior; no new motion is needed for this feature. |
| **Total** | **27 / 32** | No axis is 2 or lower. |

## Build handoff

- **Target:** existing React/Vite SPA in the existing FastAPI single-origin service.
- **System:** Radix UI + shadcn/ui primitives themed exactly with `.ulpi/design/DESIGN.md`; do not redesign or reimplement the established design system.
- **Engineering brief:** implement the catalog/connection/price review/route and credit UI from this document; connect only to authenticated same-origin APIs; do not use fixture data in production views.
- **Acceptance:** all states above; mobile/desktop keyboard and screen-reader QA; price-source/version provenance; operator/developer authorization boundaries; no secret/prompt exposure; screenshots at phone/tablet/desktop for review before deploy.
