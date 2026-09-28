---
project: Sponsored Provider
register: product
aesthetic_direction: technical / community developer console
color_strategy: committed
design_system: Radix UI + existing project components, themed with DESIGN.md
design_variance: 5
motion_intensity: 2
visual_density: 6
---

> **Superseded (2026-09-28):** this zinc/red refresh is replaced by the Ayu-dark console direction in `.ulpi/design/DESIGN.md` and `docs/superpowers/plans/2026-09-28-ai-hackclub-theme-redesign.md`. Kept as a historical record; do not implement.

# Hack Club AI-inspired portal refresh

## Job and audience

Refresh the complete signed-in Sponsored Provider experience for two audiences: the operator protecting sponsored upstream capacity, and invited developers using personal API keys. The interface must make each audience's next useful action and remaining allowance obvious without implying that the portal is Hack Club AI or shares its authentication, balances, or backend.

## Outcome and proof

- A developer can see monthly allowance remaining, create a key, choose approved models, copy an OpenAI-compatible example, and inspect their own request history.
- An operator can see aggregate usage, manage people and invites, approve/provider-map models, review pricing, and reach abuse/stop controls quickly.
- Period, currency, ownership, and whether usage is estimated or upstream-reported remain explicit.
- Existing invite-only local username/password auth, role separation, `/v1` compatibility, upstream credential secrecy, append-only request history, and no-prompt-storage rules remain unchanged.

## Reference DNA

Source reference: [Hack Club AI repository](https://github.com/hackclub/ai). Its layout source defines a zinc-charcoal canvas, Hack Club red accent, Google Sans, a compact top header, centered content, compact statistic strips, rounded surfaces, direct quick links, and a copyable first-call example. Its [dashboard](https://github.com/hackclub/ai/blob/main/src/views/dashboard.tsx), [header](https://github.com/hackclub/ai/blob/main/src/views/components/Header.tsx), [keys page](https://github.com/hackclub/ai/blob/main/src/views/keys.tsx), and [activity page](https://github.com/hackclub/ai/blob/main/src/views/activity.tsx) provide concrete spacing and hierarchy references.

- **Take:** `#18181b` page background, `#27272a` surface, `#ec3750` Hack Club red, `#d62640` hover red, `#fafafa` heading, `#d4d4d8` body text, and `#303035` subtle border; top navigation; `max-w-6xl` content; clear stat strip; action-first quick links; table-first activity; copyable integration example.
- **Take:** header `max-w-7xl`, `px-4`, `py-6`; content `max-w-6xl`, `px-4`, `py-8`; stat cells `p-6`; 2-column stats on narrow screens and 4 columns at large widths; page sections separated by `mb-12`; 2px strong card borders; 16px model-card and 24px prominent statistic-card radii; pill primary actions.
- **Reject:** Hack Club AI logo/name and copy, Hack Club OAuth, its shared-user key assumptions, unrelated Replicate/global-stats products, and any weakening of Sponsored Provider's role/privacy/budget boundaries.
- **Synthesis:** the familiar Hack Club developer-console frame surrounds Sponsored Provider's distinct per-user allowance, multi-provider catalog, and operator safeguards. The $7 USD monthly allowance is per developer, shared across that developer's keys, with provider-wide stops remaining a separate ceiling.

## Locked visual proposal

The HCAI-inspired palette and scales below replace the previous yellow/navy visual lock in `.ulpi/design/DESIGN.md`; that file remains the single token authority for implementation.

| Token role | Value | Application |
|---|---|---|
| Canvas | `#18181b` | Page background |
| Surface | `#27272a` | Tables, cards, menus |
| Elevated | `#303035` | Dialogs and raised surfaces |
| Accent | `#ec3750` | Primary action, selected state, key highlight |
| Accent hover | `#d62640` | Hover/pressed action fill |
| Heading | `#fafafa` | Main labels and headings |
| Body | `#d4d4d8` | Reading text |
| Subtle border | `#303035` | Decorative dividers |
| Strong border/focus | `#71717a` / accent focus ring | Inputs, selected controls, keyboard focus |
| Accent text | `#ff8495` | Small links/status text requiring higher contrast |
| Primary-button text | `#101114` | Contrast-safe text on Hack Club red |
| Success | `#22c55e` | Healthy/success with a text label |
| Warning | `#f59e0b` | Approaching limit with a text label |
| Danger text | `#f87171` | Error/stopped text on dark surface; red fills stay `#ec3750` |
| Info | `#60a5fa` | Informational state with a text label |

Contrast checks: `#fafafa` on canvas 16.97:1 and surface 14.27:1; `#d4d4d8` on canvas 11.99:1 and surface 10.08:1; accent-text `#ff8495` on surface 6.37:1; `#101114` on accent fill 4.70:1. Success/warning/info tokens remain above 4.5:1 on both surfaces. Danger text uses `#f87171` (5.38:1 on surface); the original red is 4.41:1 on canvas and 3.71:1 on surface, so use it as a fill or large/icon accent rather than small text. The original subtle border is not the only boundary for important controls. Pair semantic colors with text/icons.

Typography follows HCAI's Google Sans hierarchy for UI, with the existing IBM Plex Mono reserved for API IDs, token values, and code. The implementation must self-host a license-permitted Google Sans distribution if available; otherwise preserve a local, metrically compatible sans and document the substitution. No new runtime font request is allowed without explicitly updating CSP and testing it.

## Page structure and interactions

### Shared shell

- Replace the fixed left rail with a compact HCAI-style top header. Keep role-specific navigation and a visible `Operator`/`Developer` context label; never conflate capabilities.
- Desktop header: max-width 7xl, `px-4 py-6`; mobile: brand, account/allowance signal, and accessible hamburger button. Mobile menu uses a focus-managed sheet/dropdown, safe-area padding, 44px minimum action targets, Escape close, and focus restoration.
- Main content: max-width 6xl, `px-4 py-8`; preserve `Skip to content`, route focus, reduced-motion support, and sticky context only where it aids the current task.
- Maintain one primary action per view. Use existing Radix primitives and tokens; no new component library.

### Developer views

- **Home:** stat strip for requests, input/output/total tokens, estimated spend; prominent `$7/month` allowance runway showing used, reserved, remaining, and reset date; one quickstart code block and quick links to Keys, Models, Activity.
- **API keys:** searchable/scan-friendly rows; key label/prefix, model policy, use/cap and period, RPM, last-used/status. Keep secret reveal once, copy feedback, edit/revoke/archive distinctions, and owner-only data.
- **Models:** provider-grouped catalog with exact public model ID, capability, input/output/cache prices where verified, and clear unavailable/unpriced states; preserve search and filters.
- **Activity:** table-first list with time, model, input/output tokens, estimated cost, result, and latency; row detail may show request ID/provider/key label/safe error category, never prompts/completions or another user's IP. Keep cursor pagination and horizontal touch scroll.
- **Quickstart:** endpoint, minimal request example, copy action, and selected model ID. Never display upstream URLs or secrets.

### Operator views

- **Overview:** global spend runway, requests/success/rejected, input/output tokens, estimated cost, provider health, recent errors/activity, and models in use. Distinguish the global stop from each developer's monthly allowance and each upstream connection cap.
- **People & keys:** searchable people table; each developer's `$7 monthly` allowance shared across keys, used/reserved/remaining, reset date, RPM, account/invite status, and quick `Disable`/`Enable` actions. Operator can change allowance and period.
- **Providers & models:** provider health/sync and model catalog; add/sync provider, review price source, approve/unpublish offer, configure route and provider cap. Keep write-only upstream credential behavior.
- **Usage / Guardrails:** table-first filters; user/model/provider breakdown; block model/IP and stop provider actions remain high-salience but confirm destructive/high-impact changes.

## Monthly allowance contract

- Default newly invited developer allowance: **$7 USD monthly**, shared across all of that developer's keys, reset at midnight Europe/Berlin on the first of each month; no rollover.
- Operators can override the amount or remove the allowance per person. User/key limits may tighten it, never raise it.
- The $7 is not a $7 cap shared by the entire service and is not the upstream/provider budget. Keep the separate global hard stop and provider connection caps visible and enforced.
- Monthly usage includes gateway-reported cost plus active reservations. Unknown pricing/usage remains unknown or conservatively reserved, never silently free.

## Responsive layout and states

- Desktop: top navigation, compact 2x2/4-column stat strip, content width and table density modeled on HCAI; operator tables remain dense but readable.
- Tablet: stat strip wraps cleanly, toolbars wrap without overlap, tables retain horizontal swipe.
- Phone: compact header/menu; 2-column stat strip where labels fit; stacked key/model rows; full-width dialogs/sheets; table swipe with hidden decorative scrollbar; quick block/disable actions remain reachable without scrolling through long descriptions.
- Every page has loading skeleton, no-data, partial/unknown data, stale, error/retry, success, and expired-session states. Do not invent sample usage.

## Accessibility and anti-slop constraints

- WCAG AA text contrast, strong input boundaries, visible keyboard focus, logical landmarks/headings, keyboard-complete menu/dialog/table controls, status labels not conveyed by color alone, reduced motion, and screen-reader announcements for asynchronous results.
- Use the red accent intentionally; avoid purple gradients, generic glass, decorative stats, nested-card stacks, fake data, and unnecessary animation.
- Preserve the existing operator/developer separation, same-origin session behavior, and no-prompt-storage guarantee.

## Acceptance criteria

1. All operator and developer routes use the same tokens and top-shell; no old yellow/navy panels remain except documented semantic status shades.
2. A developer can see the `$7/month` personal allowance and reset, create an all-approved or selected-model key, copy a working OpenAI example, and inspect only their own activity.
3. An operator can review/adjust a person's monthly allowance and quickly navigate to provider/model/user safeguards.
4. Existing provider/API behaviors remain unchanged; no OAuth route/UI is re-enabled.
5. Month-boundary, concurrent reservation, previous allowance/history preservation, and per-user isolation tests pass.
6. Desktop (1440px), tablet (768px), and phone (390px) captures show no overflow, clipped menus, or inaccessible actions.

## Direction contract

**THESIS:** Make sponsored usage and the next action obvious without pretending to be Hack Club AI.
**OWN-WORLD:** Zinc charcoal, Hack Club red, Google Sans hierarchy, compact navigation, rounded data surfaces; Sponsored Provider's role and budget labels.
**STORY:** Developers see monthly credit, keys, approved models, and first-call setup; operators see shared exposure and act on people/providers.
**FIRST VIEWPORT:** Developer: stat strip, `$7/month` runway, quickstart. Operator: global runway, health, recent usage, safeguard path.
**FORM:** HCAI's user-pinned developer-console grammar; seed reference `dca049c3` is subordinate to the brief.
**FINISH:** unreviewed and undocumented is unfinished; this build ends with the finish review, the verdict, DESIGN.md, and every shipping raster carrying its provenance

## Design preflight (planning-stage)

- **Identity:** one dark-zinc/Hack Club red token system, one Google Sans + IBM Plex Mono typography system, one radius scale, and one top-navigation grammar; exact HCAI logo/copy is not reused.
- **Anti-slop:** source-specific content and provider ownership make this a Sponsored Provider console, not a generic admin shell. The source's quickstart/stat-strip/card patterns are used only where they serve the same task; no new decorative data or OAuth options.
- **States/flows:** auth, account allowance, key creation, provider sync, catalog price approval, request activity, and guardrail failures retain loading/empty/partial/error/success paths.
- **Accessibility:** specified contrast ratios, dark-text primary button, stronger control borders, visible focus, 44px touch targets, keyboard menu/dialog behavior, text labels for statuses, and reduced motion.
- **Layout:** topbar, 2/4-column metric strip, HCAI content widths, table-first activity, catalog card/list view, and compact phone navigation provide distinct structures without a nested-card wall.
- **Cognitive load:** no more than five links per role; one primary action per view; advanced provider routing and pricing remain in operator context.
- **Planning self-critique (spec only):** distinctiveness 3/4; hierarchy 3/4; consistency 4/4; accessibility 3/4; state coverage 4/4; copy 4/4; restraint 3/4; motion motivation 3/4. **Total 28/32.** The visual scores are provisional until implementation captures are reviewed at 1440px, 768px, and 390px.
