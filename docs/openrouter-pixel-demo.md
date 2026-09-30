# Pixel Router UI Demo

This branch contains two related frontend changes:

1. The existing developer/operator portal keeps its current routes, API client, authentication, key lifecycle, guardrails, and backend contracts, but loads `frontend/src/ui/pixel-dashboard.css` after the existing stylesheet to apply the new dense navy/violet dashboard system.
2. A populated visual showcase is available at `/demo` (or with `?demo=1`) so the 1920px composition can be reviewed without requiring a logged-in account or live telemetry.

## Launch

From `frontend/`:

```bash
npm install
npm run dev
```

Then open:

```text
http://127.0.0.1:5173/demo
```

The `/demo` screen intentionally uses clearly labeled **Demo data**. It does not replace or feed production data. Navigate to the ordinary `/developer` or `/operator` routes to exercise the real portal and backend behavior with the same visual theme.

## Visual target

- Primary canvas: 1920×1080
- Fixed 272px left rail on large desktops
- Near-black/navy surfaces with 1px cool-blue borders
- Violet primary accent with cyan/green status/data accents
- Compact mono-heavy typography and restrained pixel details
- Small 4–6px corner radii
- Dense tables/cards rather than oversized SaaS spacing
- 1280px desktop fallback with stacked secondary panels and horizontally scrollable data surfaces
