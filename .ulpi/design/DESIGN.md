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

| role | OKLCH | hex | use |
|---|---|---|---|
| background | 0.18 0.025 255 | #171a24 | page canvas |
| surface | 0.23 0.028 255 | #222633 | panels |
| elevated | 0.28 0.032 255 | #2b3040 | menus/dialogs |
| text | 0.96 0.018 95 | #f1f0ea | primary text |
| muted | 0.74 0.035 250 | #a7adbd | secondary text |
| border | 0.40 0.030 255 | #5a6073 | dividers/focus |
| accent | 0.78 0.17 92 | #e5d75b | budget/action accent |
| success | 0.70 0.13 155 | #55bd8a | healthy/live |
| warning | 0.78 0.16 75 | #e8a84c | approaching limit |
| danger | 0.68 0.18 28 | #ed765e | stopped/error |
| info | 0.70 0.12 245 | #8ba9ed | informational |

Contrast checked against the locked backgrounds: primary text is 15.20:1 on background and 13.20:1 on surface; muted text is 7.73:1 and 6.72:1; accent is 11.74:1 and 10.20:1. Success, warning, danger, and info are each above 4.5:1 on the background and surface. Semantic colors are always paired with labels/icons, never used as the only status signal.

## Type (locked)

| role | family | use |
|---|---|---|
| display | Cabinet Grotesk, fallback sans-serif | page/view headlines |
| body | IBM Plex Sans, fallback sans-serif | explanatory text/forms |
| utility | IBM Plex Mono, fallback monospace | IDs, timestamps, metrics, API values |

## Icons (locked)

Use Lucide icons only. Pair every status icon with text; no icon-only destructive actions. Use the same 1.75px stroke weight and 16/18/20px sizing steps across both portals.

## Scales (locked)

- spacing: 4px base; 4, 8, 12, 16, 24, 32, 48, 64
- radius: 4px controls, 8px panels, 12px modal only
- motion: 120ms feedback, 240ms panel transitions; `cubic-bezier(0.16, 1, 0.3, 1)`; no bounce; honor reduced motion
- focus: 2px solid accent with 3px offset
- breakpoints: 640px, 768px, 1024px, 1280px

## Voice

Technical, direct, non-alarmist. Use short, human wording. Actions use consistent verbs: `Create`, `Save`, `Disable`, `Revoke`, `Archive`, `Block`, `Resume`. Explain whether a figure is a local estimate or provider-reported amount. Never imply the portal can see or control upstream facts it cannot verify. Never rely on color alone.

## Inspiration synthesis

- OpenRouter: take the readable usage summary, model catalog, key controls, and provider-aware usage breakdown. Reject its marketplace breadth and organization features that a small sponsored gateway does not need yet.
- Hack Club AI: take the direct OpenAI-compatible quickstart and student-friendly first-call path. Reject assumptions that every user shares one credential or one undifferentiated activity log.
- Existing provider: retain budget guardrails, upstream secrecy, model allowlists, and the usage runway. Replace the owner-only admin-token experience with role-aware sessions and user-scoped pages.

## Layout rules

- Use a persistent desktop sidebar with no more than five primary destinations per role. On mobile, use a compact bottom bar plus a `More` sheet.
- Prefer a stat strip, chart with a useful legend, and table-first activity views. Do not stack nested cards or duplicate every figure in multiple widgets.
- Operator screens can be dense but must keep one primary action per view. Developer screens should foreground the model/key setup and personal allowance.
- Dense tables use server-side filters and pagination; preserve horizontal swipe on mobile while hiding decorative scrollbars.
- Request detail never displays prompt or completion text.

## Consistency rule

Every screen must read as the same product if placed side by side.
