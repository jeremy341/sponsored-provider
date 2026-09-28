---
project: Sponsored Provider
register: product
aesthetic_direction: technical / utilitarian
color_strategy: committed
design_system: Radix UI + shadcn/ui, themed with project tokens
design_variance: 6
motion_intensity: 2
visual_density: 6
---

## Design Read

A student-scale AI gateway that feels like a dependable instrument: quiet surfaces, clear ownership, visible usage, and a safe next action for both operators and developers.

## Signature

The usage runway is the signature. It shows the operator’s shared provider ceiling and each developer’s personal allowance with the same visual grammar. It makes the relationship between shared capacity and individual usage understandable without turning every screen into a chart wall.

## Color (locked)

The signed-in portals use the approved HCAI-inspired zinc/red system. These values are the implementation authority in `frontend/src/ui/styles.css`.

| role | hex | use |
|---|---|---|
| canvas | #18181b | page background |
| surface | #27272a | cards, tables, and menus |
| elevated | #303035 | dialogs and raised surfaces |
| heading | #fafafa | primary text |
| body | #d4d4d8 | body and secondary text |
| quiet | #a1a1aa | tertiary labels |
| border | #303035 | dividers; pair with fill for control boundaries |
| strong border | #71717a | inputs and important boundaries |
| accent | #ec3750 | primary action and selected state |
| accent hover | #d62640 | hover and pressed primary action |
| accent text | #ff8495 | small accent text and links |
| success | #22c55e | healthy/success state |
| warning | #f59e0b | approaching limit or incomplete coverage |
| danger | #f87171 | error/stopped text |
| info | #60a5fa | informational state |

Contrast checks on the approved palette: `#fafafa` is 16.97:1 on canvas and 14.27:1 on surface; `#d4d4d8` is 11.99:1 and 10.08:1; `#ff8495` is 6.37:1 on surface; `#101114` on the accent fill is 4.70:1. Use semantic status colors with text or icons, never as the only status signal. The accent red is for fills, large marks, and selected states; use accent text for small text on dark surfaces.

## Type (locked)

| role | family | use |
|---|---|---|
| UI | IBM Plex Sans, self-hosted via Fontsource | headings, body, labels, and controls; local substitute for the reference Google Sans hierarchy |
| utility | IBM Plex Mono, self-hosted via Fontsource | IDs, timestamps, metrics, and code |

Do not add remote font requests or change the Content Security Policy for typography without a separate approved task.

## Icons (locked)

Use Lucide icons only. Pair every status icon with text; no icon-only destructive actions. Use the same 1.75px stroke weight and 16/18/20px sizing steps across both portals.

## Scales (locked)

- spacing: 4px base; 4, 8, 12, 16, 24, 32, 48, 64
- radius: 8px controls and menus, 16px panels/dialogs, 24px prominent metric strip
- motion: 120ms feedback, 240ms panel transitions; `cubic-bezier(0.16, 1, 0.3, 1)`; no bounce; honor reduced motion
- focus: 2px solid accent with 3px offset
- breakpoints: 640px, 768px, 1024px, 1280px

## Controls and data color

- Native `select` controls share the same zinc surface, strong boundary, 8px radius, dark option palette, and visible accent focus. Filters keep the platform arrow; only the workspace switcher uses a custom chevron wrapper and suppresses the native arrow with matching right padding.
- Selects have distinct hover and disabled treatments. Disclosure buttons such as provider groups expose `aria-expanded` and have visible hover, pressed, and keyboard-focus states.
- On phone widths, model-ID copy, catalog show-all, code-language tabs, analytics tabs, and selects have at least 44px hit areas.
- Charts use Hack Club red with zinc neutrals (`--chart-primary`, `--chart-secondary`, `--chart-tertiary`, `--chart-muted`, `--chart-grid`). Do not reuse warning/error colors as decorative series; semantic success, warning, danger, and info remain reserved for status and coverage meaning.

## Voice

Technical, direct, non-alarmist. Use short, human wording. Actions use consistent verbs: `Create`, `Save`, `Disable`, `Revoke`, `Archive`, `Block`, `Resume`. Explain whether a figure is a local estimate or provider-reported amount. Never imply the portal can see or control upstream facts it cannot verify. Never rely on color alone.

## Inspiration synthesis

- OpenRouter: take the readable usage summary, model catalog, key controls, and provider-aware usage breakdown. Reject its marketplace breadth and organization features that a small sponsored gateway does not need yet.
- Hack Club AI: take the direct OpenAI-compatible quickstart and student-friendly first-call path. Reject assumptions that every user shares one credential or one undifferentiated activity log.
- Existing provider: retain budget guardrails, upstream secrecy, model allowlists, and the usage runway. Replace the owner-only admin-token experience with role-aware sessions and user-scoped pages.

## Layout rules

- Use the compact top header with no more than five primary destinations per role. On mobile, use the compact header and accessible navigation sheet.
- Prefer a stat strip, chart with a useful legend, and table-first activity views. Do not stack nested cards or duplicate every figure in multiple widgets.
- Operator screens can be dense but must keep one primary action per view. Developer screens should foreground the model/key setup and personal allowance.
- Dense tables use server-side filters and pagination; preserve horizontal swipe on mobile while hiding decorative scrollbars.
- Request detail never displays prompt or completion text.

## Consistency rule

Every screen must read as the same product if placed side by side.
