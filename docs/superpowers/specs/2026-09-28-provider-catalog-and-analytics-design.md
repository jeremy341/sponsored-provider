# Provider Model Catalog and Usage Analytics Design

Status: proposed for owner review. No implementation is authorized by this document alone.

## Intent

Make the provider feel like a clear model marketplace for developers and a reliable control console for the operator. Borrow Hack Club AI's model discovery and detail-page flow, not its brand or service-specific behavior. Rework usage charts with shadcn's composable chart pattern while keeping our existing data, auth, cost, and privacy rules authoritative.

The user selected **current calendar month** as the default model-spend chart range. Monthly windows use `Europe/Berlin`, consistent with the developer allowance reset.

## Success criteria

1. A developer can quickly search or browse one card per published provider-brand/canonical-model offer, understand its verified rates and capabilities, open a stable detail URL, and copy a correct OpenAI-compatible example.
2. The model detail page shows only known, trustworthy metadata; unavailable prices or technical facts are never represented as zero or invented.
3. Request/token/spend trends and model-spend distribution use the same server-defined period and role scope. A spend chart only claims to represent a total when its model segments reconcile to that total.
4. The operator retains full provider, routing, approval, budget, invitation, people, usage, and safeguard controls. Developer data remains scoped to the authenticated developer.
5. The refreshed experience remains usable with keyboard/screen readers and at phone, tablet, and desktop widths.

## Frontend design direction

- **Aesthetic:** “Provider Atlas” — a calm, information-dense model exchange inside an operational console. Keep the currently shipped zinc/red system and IBM Plex typography; the catalog should feel more like a precise technical index than a marketing grid.
- **Purpose and tone:** help developers compare cost/capability and get a working request quickly; help operators diagnose and control routing without mixing role-specific data. Trustworthy and direct, not playful or sales-oriented.
- **Differentiation anchor:** every model card pairs provider provenance and canonical ID with a compact, verified price band. The identity/pricing row is the recognizable signature; red is reserved for the primary action, active state, and public ID rather than decorative gradients.
- **Spatial system:** preserve the current centered, max-width console frame and 8px spacing rhythm. Use a responsive 3/2/1-column model grid, stable card heights, and side-by-side analytics only where the chart legend remains readable.
- **Motion:** restrained disclosure/route transitions only; respect `prefers-reduced-motion`. Do not add animation solely for decoration.
- **DFII:** aesthetic impact 4, context fit 5, implementation feasibility 4, performance safety 4, consistency risk 2; score **15/15** using the frontend-design rubric. Risk is controlled by reusing the established palette/type/layout and adding only chart primitives, not a second design system.

## Current product baseline

The portal is a same-origin FastAPI + React/Vite application with a role-aware shell. Existing developer routes are `/developer`, `/developer/keys`, `/developer/models`, `/developer/activity`, and `/developer/quickstart`. Operator routes are `/operator`, `/operator/people`, `/operator/providers`, `/operator/usage`, and `/operator/guardrails`.

The model catalog already groups by provider and supports search, capability filtering, and input-price sorting. Selecting **Details** opens a dialog with the public model ID, verified input/output/cached-input rates, price provenance, and one cURL example. `ModelRecord` does not currently provide description, context-window, or max-output fields.

The dashboards already show request/token/spend trends with a 14-day range and a request/token/spend switch. The trend is currently drawn with custom CSS bars. The model table uses `topModels`, which is all-time and capped at eight models. It must not be reused as the denominator or complete data source for a model-mix chart.

Current invariants to preserve:

- local username/password authentication and invite-only account creation; no OAuth activation;
- operator/developer role separation and owner-scoped developer keys/activity;
- one public offer per provider brand and canonical model, with duplicate routes merged within that brand; the same model from different brands remains separately selectable and provider-scoped;
- operator-controlled provider/model approval and availability, per-key model allowlists and spend caps, and the shared $7/month allowance default for newly invited developers;
- server-side budget reservations, provider/global safeguards, append-only historical usage snapshots, and one-worker SQLite deployment assumptions;
- no stored or displayed prompts/completions, and no upstream credentials/base URLs in the developer portal;
- historical usage remains visible when a key, provider route, or model is disabled or removed.

## Reference audit: what to adopt and what to change

Hack Club AI's current source organizes the catalog by model categories, shows compact model cards with a name, short description, and copyable model ID, and links each card to a model-detail route. Its detail page has a model header, price/context summary cards, collapsible technical details, and language tabs for code examples. Its wildcard route accepts model IDs containing slashes. [Catalog view](https://github.com/hackclub/ai/blob/main/src/views/models.tsx) · [Detail view](https://github.com/hackclub/ai/blob/main/src/views/model.tsx) · [Model routes](https://github.com/hackclub/ai/blob/main/src/routes/models.tsx)

The header uses compact horizontal navigation, a current-spend indicator, and a mobile menu; the dashboard surfaces summary metrics, quick links, quickstart, and recent usage. Our current shell already adopts a similar high-level hierarchy, but keeps separate role navigation. [Header](https://github.com/hackclub/ai/blob/main/src/views/components/Header.tsx) · [Dashboard](https://github.com/hackclub/ai/blob/main/src/views/dashboard.tsx) · [Activity](https://github.com/hackclub/ai/blob/main/src/views/activity.tsx)

The authenticated Hack Club AI pages were not publicly renderable in this audit; the observations above come from its current public repository `main`. Its public landing page was accessible. Do not copy Hack Club's logo, name, OAuth flow, exact copy, OpenRouter SDK, or `/proxy/v1` endpoint. Its model route refetches the full upstream catalog on detail navigation; our detail flow should resolve from our published catalog instead.

## Developer model catalog

### Listing

- Keep the existing searchable, filterable catalog and provider/capability facets.
- Present responsive cards grouped by **provider brand**. Merge duplicate upstream model IDs into one offer/card within that brand; show a compact “N active routes” indicator where known. If two provider brands serve the same canonical model, keep separate cards and provider-scoped public IDs as specified by the catalog-routing design.
- Each card should show display name, canonical public ID, text/vision capability, availability, and verified input/output rates per million. Cached-input pricing may appear as a compact third rate when verified. The price source/verification status must remain visible.
- Show only a small initial set per group on narrower screens with a clear “Show all” control; preserve search and sorting for large catalogs.
- Use a semantic article/card with a primary detail link and separate copy-ID button. Do not put a button inside an anchor.
- Keep operator-only actions such as approval, route enable/disable, and provider controls in operator routes.

### Detail route and content

- Add a deep-linkable developer detail route under `/developer/models/*`. The wildcard accommodates canonical IDs that contain `/`; parsing, URL encoding, and unknown IDs must be tested. The detail page's back link returns to the catalog and preserves its search/filter state.
- Resolve details from the provider-brand-scoped, database-backed published offer. Do not call each upstream from a developer page. Return only public catalog data and safe display labels for active same-brand routes; never return credentials or internal URLs.
- Detail hierarchy: breadcrumb; model name/vendor/capability/availability; copyable public ID; verified input/output/cached-input rates and provenance; optional technical details; code examples.
- Show context window, max output, description, tokenizer, or modality details only when the provider supplies trustworthy metadata or an operator has explicitly verified it. The initial version should not invent or synthesize model descriptions.
- For models no longer published, historical request rows remain intact. A historical detail link may show a clearly marked unavailable/tombstone view based on request-time snapshots; it must not make the model callable again.

### Code examples

- Provide cURL, Python, and JavaScript/OpenAI-SDK tabs with copy controls.
- Build every snippet from the selected canonical model ID and the portal's own `window.location.origin + "/v1"` base URL. Use a placeholder such as `YOUR_API_KEY`; never embed a real secret.
- Only show endpoints/payloads supported by our gateway. Chat completions are the baseline. Show a vision payload only for a model marked vision-capable and after the gateway's image-input behavior is covered by tests. Do not add embeddings or image-generation examples unless those endpoints are implemented and verified.
- Share snippet generation with Quickstart where practical so base URLs and request shapes cannot drift.

## Usage analytics and shadcn charts

Use shadcn's chart composition—Recharts with `ChartContainer`, configured tooltip/legend, CSS-variable colors, and `accessibilityLayer`—inside a small local chart component. The official chart is a copy-and-compose pattern built on Recharts; do not replatform the existing Vite/CSS app or initialize Tailwind just for charts. [shadcn chart docs](https://ui.shadcn.com/docs/components/base/chart) · [Pie examples](https://ui.shadcn.com/charts/pie)

### Shared analytics window

- Default dashboard analytics to **This month** in `Europe/Berlin`.
- Offer a bounded selector such as This month, Last 7 days, Last 30 days, and Last 90 days. One selection drives the dashboard period summary, daily trend, top-model ranking, and model-mix chart.
- Keep the developer's monthly allowance runway separate and always tied to its server-computed calendar-month window; changing a chart range must not alter a limit/reset.
- Label any lifetime totals separately. Do not place an all-time summary beside a current-month chart without explicit labels.

### Visualizations

- Replace the custom CSS usage bars with a responsive shadcn-style time-series chart. Keep a control for Requests, Tokens, and Spend; display correct units and a tooltip with date/value.
- Add a model-spend donut to both developer and operator dashboards. Its data source is a complete, server-scoped aggregation for the same selected range—not the current all-time/top-eight `topModels` payload.
- Percentage is `model spend / total known model spend` for that period. Group every model below 3% into one **Other models** slice. Keep percentages in the legend; tooltips can show exact USD plus percentage.
- Aggregate monetary values server-side with the existing nano-USD/request-time cost snapshots, then return decimal USD strings. Avoid floating-point pie totals drifting from the displayed total.
- If all requests in the period have known cost, chart segments must sum to the displayed selected-period spend (100%). If any cost is unknown, never treat it as zero: show cost coverage and label the donut as known/priced spend only, or an incomplete state if the total cannot be reconciled. Do not silently claim full coverage.
- Provide a semantic data table alternative for assistive technology, explicit empty/loading/error states, keyboard-accessible controls, and no sample/fabricated data.
- Use a restrained palette derived from the existing red/zinc theme; no unbounded rainbow palette. Ensure the legend is usable on mobile without page-level horizontal overflow.

### Backend/data contract needed

The dashboard API currently returns a fixed 14-day timeseries and all-time `topModels` capped at eight. The design therefore requires a role-scoped period query and a complete model breakdown, including total priced spend, per-model request/token/spend totals, and an unknown-cost/coverage signal. Developer responses must aggregate only that developer; operator responses may aggregate service-wide. Use event snapshots so removing a model or key cannot erase historical chart data.

Suggested response contract (names illustrative):

```json
{
  "period": { "key": "current_month", "from": "...", "to": "...", "timezone": "Europe/Berlin" },
  "summary": { "requests": 0, "inputTokens": null, "outputTokens": null, "knownSpendUsd": "0", "unpricedRequests": 0 },
  "series": [],
  "modelSpend": [{ "modelId": "...", "providerName": "...", "spendUsd": "0", "requests": 0, "tokens": null }]
}
```

The example is a shape, not sample UI data. Unknown fields remain null/explicit; there is no assumption that missing token/cost fields equal zero. Existing activity filters and owner scoping remain unchanged.

## Routes and surface composition

Keep the present role split and navigation. Developer catalog/detail/activity remain developer-only; Providers, People & keys, Usage, and Guardrails remain operator-only. A detail route must be protected by the same developer session gate as the catalog. The owner may inspect safe provider route state in operator pages, but developer pages must not expose base URLs, credentials, or connection internals.

Dashboard layout recommendation:

- Developer: period-labeled summary; personal allowance card; usage trend + model-spend mix; quick links/Quickstart; keys and recent activity; model usage ranking.
- Operator: global guardrail/runway and provider health; period-labeled aggregate trend + model-spend mix; recent activity; existing provider/people/usage controls.
- Desktop uses paired analytics cards; tablet stacks or uses a balanced two-column grid; phone stacks charts and shortens legends while retaining keyboard access.
- Preserve all current invite/account, key, provider sync/pricing, model approval/routing, IP/model block, audit, rate-limit, and limit-management behavior.

## Non-goals

- Replacing the local username/password + invitation gate with Hack Club Auth.
- Copying Hack Club branding, marketing text, external SDK, OAuth behavior, or any API route that our service does not support.
- Storing prompts/completions or exposing them in request detail pages.
- Rebuilding every component on shadcn/Tailwind or changing the deployed service topology.
- Rewriting provider/route policy or treating the $7 allowance as a global service cap.

## Implementation acceptance criteria

1. Model cards open deep-linked details and back navigation restores catalog filters; slash-containing, provider-scoped IDs work on direct load/refresh.
2. Cards/details show only database-published offers, merge duplicate routes within the same brand, and never merge separate provider brands.
3. Snippets match the actual `/v1` contract, use placeholders, copy correctly, and expose no secret.
4. Current-month, 7-day, 30-day, and 90-day aggregation tests verify timezone boundaries and identical period filters across summary, trend, and model breakdown.
5. For fully priced fixtures, model shares total 100% and the dollar sum matches the period total; `<3%` models aggregate into one Other slice. Unknown-cost fixtures are visibly incomplete and never counted as free.
6. Historical model usage still renders when the current catalog entry or key is removed.
7. Role-boundary, loading/empty/error, keyboard/accessibility, and responsive tests pass for developer and operator views.
8. All existing authentication, key limits, provider controls, monthly allowance, and historical data tests continue to pass.

## Decisions carried forward

- Default analytics range: current month, selected by the user; use `Europe/Berlin` as the recommended period boundary to align with the monthly allowance.
- Model-mix metric: spend distribution, not request count; chart denominator is the same selected period's known spend.
- Model presentation: one public card per provider-brand/canonical-model offer; merge same-brand routes, keep cross-brand offers distinct, and show route provenance in details.
- Metadata: show provider/operator-verified values only; do not hallucinate descriptions or technical specifications.
- Auth and all currently deployed product features remain unchanged.

## References

- Hack Club AI public landing page: https://ai.hackclub.com/
- Model cards: https://github.com/hackclub/ai/blob/main/src/views/models.tsx
- Model detail and code tabs: https://github.com/hackclub/ai/blob/main/src/views/model.tsx
- Wildcard model routing: https://github.com/hackclub/ai/blob/main/src/routes/models.tsx
- Navigation/dashboard/activity: https://github.com/hackclub/ai/blob/main/src/views/components/Header.tsx
- shadcn chart composition: https://ui.shadcn.com/docs/components/base/chart
