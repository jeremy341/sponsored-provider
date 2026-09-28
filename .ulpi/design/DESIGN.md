---
project: Sponsored Provider
register: product
aesthetic_direction: retro-futuristic / after-hours pixel operations console
color_strategy: full-palette
design_system: Radix UI and existing React/Vite components themed with Poorup tokens
design_variance: 7
motion_intensity: 2
visual_density: 7
---

# Design Read

An after-hours control room for sponsored AI access: the exact Poorup palette and crisp pixel geometry make the provider feel like part of the same world, while its information hierarchy remains a clear operations tool rather than a board-game screen.

## Signature

The usage runway is a segmented ledger instrument: gold tick marks, a crisp SVG position marker, and explicit used/reserved/remaining labels. The same grammar represents a developer's personal allowance and the operator's shared upstream exposure, but their labels and scopes never collapse into one another.

## Inspiration

- **Poorup:** take the rendered near-black teal surfaces, warm gold ink and structural rules, brick-red action color, square geometry, Pixelify/Silkscreen type character, and crisp pixel-grid SVG craft. Reject its game logo, board art, mascots, cursor reticle, and gameplay copy; create a provider-specific icon family in the same SVG grammar.
- **Synthesis:** preserve Poorup's visual rules exactly, but let provider ownership, user limits, model prices, request history, and safeguards determine the console's content and layout.
- **Authority:** the checked-out Poorup stylesheet's rendered CSS tokens are the source for exact values. The Poorup design notes and stylesheet disagree on the bright-red token; this lock uses the stylesheet's rendered `#E36B5F` and records the discrepancy for future reconciliation.

## Color (locked)

| Role | Value | Use |
|---|---|---|
| Canvas | `#01070A` | App background |
| Chrome | `#020A0D` | Header and navigation surfaces |
| Panel | `#071314` | Primary sections, cards, tables |
| Raised panel | `#09191A` | Menus, selected rows, raised controls |
| Deep surface | `#030C10` | Code, inset areas, quiet table cells |
| Board tile / center | `#061011` / `#031D1E` | Limited decorative/chart framing only |
| Inset / card / board frame | `#04100F` / `#071516` / `#020C0D` | Inset controls, ledger panels, rare framed surfaces |
| Surface hover / board hover | `#0B1C1D` / `#0A1A1A` | Hovered rows and board items |
| Button hover / pressed | `#0C1C1D` / `#050F10` | Secondary button/icon-control feedback; distinct from general row hover |
| Disabled / selected / active | `#071011` / `#0C1F1C` / `#0D211F` | Non-color-only control state pairing required |
| Special / card highlight | `#0C2524` / `#0B2020` | Limited emphasis surfaces |
| Primary ink | `#F0D9AC` | Highest emphasis |
| Body ink | `#E8D3AB` | Headings and readable text |
| Muted ink | `#A79D7D` | Secondary copy and metadata |
| Gold accent steps | `#CFA75F`, `#C88F2E`, `#9B783D`, `#5C5033` | Selection, rules, markers, quiet emphasis |
| Action red | `#AF2A21` | Primary action fill and urgent action state |
| Red hover / pressed | `#BE3126` / `#98231C` | Action feedback |
| Bright red | `#E36B5F` | Large/icon-sized secondary emphasis only |
| Success | `#35A653` | Success/healthy state, paired with a label/icon |
| Information blue | `#286EA1` | Large markers or tinted surfaces, not small text |
| Olive | `#78894F` | Secondary icon/data category |
| Default/active rule | `#5C5033` / `#C88F2E` | Borders, dividers, selected rules |
| Dark/subtle/strong/shadow rule | `#1D2927` / `#3A382A` / `#6B5A36` / `#101916` | Structural hierarchy and inset edges |
| Error surface/border/ink | `#170807` / `#AF2A21` / `#F0B1A6` | Error notice with label/icon |
| Action edge/shadow | `#D05A49` / `#721C18` | Only for small button-edge detailing |

Contrast checks against rendered Poorup surfaces: `#F0D9AC` on canvas `#01070A` is 14.70:1; `#E8D3AB` on panel `#071314` is 12.89:1; `#CFA75F` on panel is 8.40:1; `#A79D7D` on panel is 6.98:1; `#35A653` on panel is 6.05:1; `#F0D9AC` on action red is 4.79:1. Action red on panel is only 2.86:1 and information blue on panel 3.45:1, so neither is small body text. Use the accessible gold/ink token for status text, pair status colors with explicit labels/icons, and use red primarily as a control fill/large mark.

## Type (locked)

| Role | Family | Use |
|---|---|---|
| Display / section (`--font-display`) | Pixelify Sans | Page and section headings; uppercase section labels where they remain readable |
| UI / body | Pixelify Sans | Navigation, controls, descriptions, and form copy; retain readable body sizing and line-height |
| Pixel utility | Silkscreen | Short micro-labels and selected compact numeric readouts only |
| Technical utility | IBM Plex Mono | Model IDs, API values, timestamps, tokens, currency, and code |

Use local font assets only after confirming their licenses and carrying required notices. Never fetch fonts at runtime. Use tabular numerals for money, token totals, time, and IDs. Do not use Silkscreen for paragraphs, helper text, or long table cells.

## Scales (locked)

- Spacing: `2, 4, 8, 12, 16, 20, 24, 32, 40px`; use no competing spacing system.
- Radius: `2px` for controls, rows, panels, and dialogs; `3px` only for small pressed/interactive details. No pills or rounded SaaS cards.
- Border: `1px` normal; `2px` selected, focus, or high-emphasis boundary.
- Surfaces: flat teal-black fills, gold hierarchy lines, a subtle inset highlight and restrained canvas-tinted shadow. No glass, gradient chrome, or large blurred glow.
- Shadow tokens: panel `0 2px 8px rgb(0 0 0 / 45%)`; inset `inset 0 1px 0 rgb(240 217 172 / 5%)`; active `0 0 8px rgb(200 143 46 / 12%)`. Keep large page content unblurred and quiet.
- Motion: hover `80–120ms`, press `60–80ms`, panels `120–160ms`; stepped/ease-out character; no bounce; honor `prefers-reduced-motion`.
- Focus: visible `2px` gold outline with `1px` offset; do not rely on accent color alone.
- Responsive checkpoints: `390px`, `768px`, `1024px`, `1280px`, and `1440px`; preserve safe areas and 44px minimum touch targets.

## Icon and texture language

- One provider-owned pixel SVG family, built from low-resolution rect/path geometry with `shape-rendering="crispEdges"`, gold/red/teal CSS variables, and a consistent 16/20/24/32px size set.
- Keep Radix primitives for accessible dialogs/tabs/menus and use these SVGs as glyphs; do not install an icon or UI library.
- Never reuse the Poorup wordmark, board squares, property art, mascots, or reticle cursor. Keep the browser's native pointer/text cursors.
- Screen-print/noise texture may appear only in restrained branding or empty-state moments. No scanline/noise overlay over dense data, code, forms, or charts.
- Recharts remains a semantic data chart rendered as SVG; theme its axis, grid, tooltip, frame, and markers. Do not rasterize it or make data harder to read for pixel effect.

## Voice and product boundaries

Direct, calm, operational. Preserve current Provider Console terminology and factual copy, adding only small console-style labels where they improve wayfinding. Keep operator/developer ownership explicit; do not imply upstream-reported cost when estimated, or show unknown cost as zero/free. Keep usernames/passwords, invitations, per-user data, upstream secrets, model policies, request history, `/v1`, and server/API behavior unchanged.

## Layout rules

- Keep the current role-specific top shell and route topology; restyle its brand, active navigation, account context, and mobile sheet in this system.
- Use ledger-like ruled sections and table-first data. Reserve framed panels for real groups; avoid repeated card grids and nested surfaces.
- Developer views foreground personal allowance, keys, model access, quickstart, and private activity. Operator views foreground shared exposure, providers/routes, people, aggregate activity, and safeguards.
- Shared controls use one button/input/select/tab/disclosure/dialog vocabulary. Status combines text/icon with color.
- `/dashboard` remains a compatibility route and receives the same visual tokens without changing its endpoint or authentication behavior in this visual pass.

## Consistency rule

Every screen must read as the same product if placed side by side.
