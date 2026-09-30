# OpenRouter-Inspired Pixel UI Demo Design

## Purpose

Build a runnable frontend demo for `sponsored-provider` that preserves the repository's existing backend contracts, role-aware routes, and core portal functionality while replacing the current visual shell with the dense dark dashboard language shown in the supplied screenshots.

The visual direction is OpenRouter-inspired in information architecture only: a persistent left navigation rail, dense data tables, compact analytics cards, comparison panels, and developer-focused controls. The surface treatment is intentionally distinct: near-black/navy canvas, restrained retro/pixel cues, 1px borders, small radii, mono-heavy typography, violet primary accents, cyan/green status/data accents, and minimal ornament.

## Success Criteria

- Primary desktop target is 1920x1080 and should look intentionally composed at that size rather than stretched from a smaller layout.
- Existing developer/operator functionality remains wired to the current API layer; the redesign must not require backend contract changes.
- Existing role separation and protected routes remain intact.
- Main portal surfaces visually match the supplied screenshots in density, spacing, panel hierarchy, navigation placement, and control sizing without copying OpenRouter branding or exact proprietary assets.
- The demo is usable at narrower desktop widths down to 1280px, with graceful compression/scrolling for data-heavy views.
- Existing frontend tests continue to pass; new tests cover shell/navigation behavior and key redesigned interactive states.

## Existing Architecture Constraints

The project already uses React 19, TypeScript, Vite, React Router, Radix UI primitives, Lucide icons, and Recharts. Existing API wrappers in `frontend/src/lib/api.ts` remain the source of truth for backend integration. Existing typed contracts in `frontend/src/contracts` remain unchanged unless a strictly frontend-only view model is required.

The current app already exposes separate developer and operator flows. Preserve that split instead of collapsing everything into one universal dashboard.

## Scope

### Developer-facing surfaces

Redesign the existing developer experience into the new shell while preserving current data/actions. The visual system should support the screenshot-style concepts for:

- Overview/dashboard
- Models/catalog
- Playground / quickstart-style request testing surface where current functionality allows it
- Activity/request history
- Usage/allowance analytics
- API keys

If the current repo does not implement one screenshot concept as an interactive backend feature, render it as a clearly frontend-only demo panel using derived/current data rather than inventing a new server endpoint.

### Operator-facing surfaces

Redesign the operator experience while preserving current administration and guardrail behavior:

- Overview
- People & keys
- Providers & models
- Usage
- Guardrails & audit

Provider health, routing, spend, incidents, and operator controls should use the same reusable cards/tables/tabs rather than page-specific styling.

## Visual System

### Canvas and surfaces

Use a four-level dark surface system:

- app canvas: approximately `#07101d`
- sidebar / page shell: approximately `#091423`
- panels: approximately `#0c1828`
- raised controls / hover states: approximately `#112039`

Use cool blue-gray 1px borders in the `#29415f` range. Avoid large soft shadows; separation should come mostly from borders, local contrast, and occasional subtle inset/highlight treatment.

### Accent colors

- primary violet: approximately `#7c4dff`
- bright violet highlight: approximately `#9b6cff`
- cyan data accent: approximately `#2dd4ff`
- success/healthy: approximately `#22e6a7`
- warning: approximately `#f2c94c`
- destructive/error: approximately `#ff557a`

Colors are semantic tokens, not one-off values inside components.

### Typography

Use the fonts already present in the repo rather than adding dependencies:

- headings / compact UI labels: Maple Mono or IBM Plex Mono
- body/readable supporting text: Noto Sans where longer text benefits from it
- pixel accents only for very small labels, badges, decorative metadata, or logo treatment; do not render entire dashboards in a low-legibility pixel font

Page title sizes should stay compact (roughly 32–36px at 1920px), panel titles roughly 16–18px, table/control text roughly 13–15px.

### Geometry and spacing

- desktop sidebar width: ~272px
- main content gutters: 28–32px at 1920px
- panel gap: 14–16px
- panel padding: 16–20px
- control height: 36–40px
- border radius: 4–6px for most surfaces; avoid pill-heavy styling except for statuses/tags
- dense tables: 44–52px rows depending on information density

Avoid excessive vertical scrolling at 1920x1080 where the supplied screenshot fits the relevant information in one viewport. Prefer grids and compact tables, but allow scrolling where the existing feature naturally requires it.

## Shell and Navigation

Create one reusable portal shell with role-specific nav definitions.

The shell contains:

- fixed left rail
- product mark/name at top
- role-appropriate navigation links with icon + label
- active item shown with violet border/background treatment
- bottom allowance/usage mini-card when allowance data is available
- main page content to the right

Do not duplicate shell markup between developer and operator areas. Route protection and auth behavior remain as currently implemented.

## Reusable UI Components

Implement or extract focused components rather than expanding the already-large `App.tsx` further:

- `PortalShell`
- `PageHeader`
- `NavItem`
- `Panel`
- `MetricCard`
- `StatusBadge`
- `DataTable` styling primitives
- `FilterBar`
- `SegmentedTabs`
- `ProgressBar`
- `MiniBarChart` / reusable chart wrappers
- `AllowanceCard`
- `EmptyState`

Use existing Radix primitives for accessible dialogs, tabs, selects, and tooltips where appropriate.

## Page Composition

### Overview

At 1920px, compose the page similarly to the supplied dashboard screenshot:

1. page title + date/range control
2. 4 compact top metric cards
3. monthly allowance progress panel
4. two-column middle area with usage-over-time chart and model-usage breakdown
5. two-column lower area with provider health and recent requests

Cards should align to a shared grid and visually terminate at similar heights.

### Models

Use a dense search/filter toolbar, followed by a featured-model row and a split main area:

- left: model table/list with price, provider, context, latency, capabilities
- right: quick compare panel when models are selected

The comparison panel is frontend presentation over existing model/catalog data. Do not add ranking claims unsupported by repo data.

### Playground / Quickstart

Where the repo currently provides quickstart/testing behavior, present it as a two-column developer workbench:

- left: prompt/request composition and result/output
- right: request configuration and token/cost breakdown

If there is no backend execution endpoint for a screenshot control, keep that control demonstrative/disabled rather than fabricating a working API.

### Activity / Logs

Reuse current activity data. At large desktop width, support a master-detail pattern:

- left: filterable request table
- right: selected request summary/details

If only one level of detail exists in the current API, show the available fields and omit unsupported tabs rather than inventing response metadata.

### Usage

Compose allowance, spend over time, model/provider breakdown, and alert state into one dense analytics page using current dashboard data.

### Providers / Operator Models

Provide compact provider rows/cards with status, latency, cost/model metadata where available. Existing operator actions stay available in the redesigned controls.

### API Keys

Keep existing create/reveal-once/edit/revoke/archive behavior intact. Use a large key table plus a right-side create/edit drawer or dialog on desktop, matching the supplied screenshot's spatial pattern without changing security semantics.

### Settings / Guardrails

Map existing operator/developer settings and guardrails into grouped panels with consistent tabs/controls. Existing dangerous/destructive actions retain confirmation behavior.

## Data and Fallback Behavior

Real API responses always take priority.

For visual-only screenshot concepts not backed by an API field, derive values only when mathematically defensible from existing data. Otherwise show an explicit neutral placeholder (`—`, `Not available`, disabled control, or empty state). Do not silently manufacture spend, health, latency, provider, or model metrics.

A demo-only mock dataset may be used only behind an explicit local development flag such as `VITE_DEMO_DATA=1`; production/default behavior must remain real-data-first.

## Responsive Behavior

The design is desktop-first.

- >= 1600px: full screenshot-like compositions and side-by-side detail panels
- 1280–1599px: compress gaps and allow secondary panels to stack where necessary
- < 1280px: preserve functionality, allow horizontal table scrolling, and collapse the sidebar using the project's existing responsive pattern if available

No mobile-first redesign is required for this demo.

## Accessibility

- keyboard-visible focus treatment using violet/cyan outline tokens
- sufficient contrast for body text and statuses
- icon-only buttons include accessible names/tooltips
- dialogs/drawers use Radix focus management where already available
- charts do not rely on color alone for meaning when a label/legend can carry it

## Testing

Preserve existing test coverage and add focused tests for:

- role-aware sidebar links
- active nav state
- allowance card rendering with real/empty data
- key-management dialog/drawer state without changing existing key lifecycle semantics
- model comparison selection behavior if introduced
- responsive shell class/state behavior where it is deterministic in jsdom

Run `npm test`, `npm run typecheck`, `npm run lint`, and `npm run build` from `frontend/` before declaring the demo complete.

## Non-Goals

- backend contract redesign
- new authentication system
- new billing engine
- new provider-routing algorithm
- fabricated operational analytics
- pixel-perfect copying of OpenRouter branding or proprietary assets
- major dependency changes

## Delivery

Work on branch `demo/openrouter-pixel-ui`.

The first deliverable is a runnable visual demo that can be launched with the existing frontend development command. It should be safe to review without changing `main`. Once approved visually, the branch can be refined or merged separately.