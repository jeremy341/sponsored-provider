---
project: Sponsored Provider Control Room
register: product
aesthetic_direction: technical / utilitarian
color_strategy: committed
design_system: native semantic HTML + CSS variables
design_variance: 5
motion_intensity: 2
visual_density: 7
---

## Design Read

An operator console that feels like a precise instrument: quiet surfaces, decisive states, and evidence before action.

## Signature

The budget rail is the signature. It is the only oversized visual element and turns spending into a physical runway: used, warning, and hard-stop markers are visible at a glance.

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

Text/UI pairings target WCAG AA: primary text on surface ≥ 7:1, muted text on background ≥ 4.5:1, semantic colors paired with text labels and never used as color-only signals.

## Type (locked)

| role | family | use |
|---|---|---|
| display | Cabinet Grotesk, fallback sans-serif | page/view headlines |
| body | IBM Plex Sans, fallback sans-serif | explanatory text/forms |
| utility | IBM Plex Mono, fallback monospace | IDs, timestamps, metrics, API values |

## Scales (locked)

- spacing: 4px base; 4, 8, 12, 16, 24, 32, 48, 64
- radius: 4px controls, 8px panels, 12px modal only
- motion: 120ms feedback, 240ms panel transitions; `cubic-bezier(0.16, 1, 0.3, 1)`; no bounce; honor reduced motion
- focus: 2px solid accent with 3px offset
- breakpoints: 640px, 768px, 1024px, 1280px

## Voice

Technical, direct, non-alarmist. Actions use consistent verbs: `Load`, `Save`, `Create`, `Disable`, `Revoke`, `Block`, `Resume`. Never rely on color alone.

## Consistency rule

Every screen must read as the same product if placed side by side.

