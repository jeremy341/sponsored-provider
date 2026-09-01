# Dashboard and provider controls

## Design Read

The dashboard is an operations surface. It should answer: what is happening, what can I safely change, and what will happen next?

## Navigation

Use five tabs: Quick view, Statistics, Keys, Safeguards, Upstreams. Keep the active tab in URL hash state where possible. The primary action is contextual: `Create key` on Keys, `Add provider` on Upstreams, `Save` on settings.

## Model picker

Use a searchable multi-select combobox, not a native 82-option select and not a flat checkbox wall.

- trigger shows `All models` or `N selected`;
- opening reveals search input, scrollable results, Select all, Clear all;
- each option has checkbox, model ID, category, and optional provider badge;
- typed IDs are accepted as removable chips after Enter;
- empty selection means inherit the global allowlist in policy editors;
- explicit `All available from this provider` is separate from empty/inherit;
- loading, empty, stale, error, and partial catalog states are visible;
- keyboard: Enter opens, arrows move, Space toggles, Escape closes, Backspace removes last chip.

## Key policy form

Group controls into three compact sections: Access (provider/model/risk), Limits (spend/RPM/tokens/concurrency), Lifecycle (approval/expiry/enablement). Each limit has `Inherit`, `Unlimited`, and `Custom` modes; numeric inputs appear only for Custom.

## Upstream form

Provider name, provider kind, base URL, and API key are entered in a dialog. The key field is write-only. After save, show `Sync models`, `Health`, and a model count. Never show the secret or place it in a URL.

## States

- locked: show dashboard shell, request operator token;
- live: show current telemetry and controls;
- empty: explain how to add provider/key;
- syncing: disable sync button and show progress label;
- stale: show last successful sync time and retry;
- error: show actionable provider error without raw credentials;
- stopped: make resume explicit and require confirmation for stop;
- mobile: stack panels, preserve 48px touch targets, horizontal-scroll tab row.

## Pre-flight result

- identity lock: pass once `DESIGN.md` is present and all updated styles use its variables;
- state coverage: pass after model sync/empty/error and modal cancel/success states are tested;
- accessibility: pass after keyboard/focus/ARIA checks;
- visual audit: fix low-contrast posture panel, reduce nested borders, and avoid a flat 82-item wall.

## Build handoff

Implement in the existing native HTML/CSS/JS dashboard. Use the locked variables above. Do not redesign the identity or introduce a second component vocabulary.

