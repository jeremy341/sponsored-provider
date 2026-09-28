import { existsSync, readFileSync } from "node:fs";
import { join, resolve } from "node:path";
import { describe, expect, it } from "vitest";

const stylesheet = readFileSync(resolve(process.cwd(), "src/ui/styles.css"), "utf8");

const fontDirectory = resolve(process.cwd(), "src/assets/fonts");

const tokenBlock = stylesheet.match(/:root\s*\{([^}]*)\}/)?.[1] ?? "";

function tokenValue(name: string): string {
  const declaration = stylesheet.match(new RegExp(`--${name}\\s*:\\s*([^;]+);`));

  expect(declaration, `missing design token --${name}`).not.toBeNull();

  return declaration?.[1].trim().toLowerCase() ?? "";
}

function lastBorderRadiusFor(selector: string, css: string): string | null {
  let value: string | null = null;

  for (const match of css.matchAll(/([^{}]+)\{([^{}]*)\}/g)) {
    if (!match[1].split(",").some((candidate) => candidate.trim() === selector)) continue;

    const declaration = match[2].match(/border-radius\s*:\s*([^;]+)/);

    if (declaration) value = declaration[1].trim();
  }

  return value;
}

describe("Poorup visual system foundation", () => {
  it("locks the shared Poorup surfaces, action colors, geometry, and spacing", () => {
    const expected = {
      canvas: "#01070a",
      chrome: "#020a0d",
      surface: "#071314",
      "surface-raised": "#09191a",
      "surface-deep": "#030c10",
      "surface-button-hover": "#0c1c1d",
      border: "var(--border-default)",
      "ink-primary": "#f0d9ac",
      "ink-body": "#e8d3ab",
      "ink-muted": "#a79d7d",
      "gold-accent": "#cfa75f",
      gold: "#c88f2e",
      "gold-muted": "#9b783d",
      "gold-quiet": "#5c5033",
      action: "#af2a21",
      "action-hover": "#be3126",
      "action-pressed": "#98231c",
      success: "#35a653",
      info: "#286ea1",
      "border-default": "#5c5033",
      "border-dark": "#1d2927",
      "border-subtle": "#3a382a",
      "border-strong": "#6b5a36",
      "radius-control": "2px",
      "radius-detail": "3px",
      "font-display": '"pixelify sans", sans-serif',
      "space-1": "2px",
      "space-2": "4px",
      "space-3": "8px",
      "space-4": "12px",
      "space-5": "16px",
      "space-6": "20px",
      "space-7": "24px",
      "space-8": "32px",
      "space-9": "40px",
    };

    for (const [name, value] of Object.entries(expected)) expect(tokenValue(name), `--${name}`).toBe(value);

    expect(tokenValue("shadow-panel")).toBe("0 2px 8px rgb(0 0 0 / 45%)");
    expect(tokenValue("shadow-inset")).toBe("inset 0 1px 0 rgb(240 217 172 / 5%)");
    expect(tokenValue("focus-outline")).toBe("2px solid var(--gold)");
    expect(tokenValue("focus-offset")).toBe("1px");
    expect(tokenValue("font-display")).toBe('"pixelify sans", sans-serif');
    expect(tokenBlock).not.toMatch(/#18181b|#27272a|#303035|#ec3750|#d62640/i);

    const definedTokens = new Set([...tokenBlock.matchAll(/--([a-z0-9-]+)\s*:/gi)].map((match) => match[1]));
    const referencedTokens = [...stylesheet.matchAll(/var\(--([a-z0-9-]+)/gi)].map((match) => match[1]);
    const missingTokens = [...new Set(referencedTokens.filter((name) => !definedTokens.has(name)))];

    expect(missingTokens).toEqual([]);
  });

  it("loads primary and utility faces from local, attributed font assets", () => {
    expect(stylesheet).toMatch(/font-family:\s*["']Pixelify Sans["']/i);
    expect(stylesheet).toMatch(/url\(["']?\.\.\/assets\/fonts\/pixelify-sans-400\.woff2["']?\)/i);
    expect(stylesheet).toMatch(/url\(["']?\.\.\/assets\/fonts\/pixelify-sans-700\.woff2["']?\)/i);
    expect(stylesheet).toMatch(/font-family:\s*["']Silkscreen["']/i);
    expect(stylesheet).toMatch(/url\(["']?\.\.\/assets\/fonts\/silkscreen-regular\.ttf["']?\)/i);
    expect(stylesheet).not.toMatch(/https?:\/\//i);

    for (const filename of ["pixelify-sans-400.woff2", "pixelify-sans-700.woff2", "silkscreen-regular.ttf"]) {
      expect(existsSync(join(fontDirectory, filename)), `local font asset ${filename}`).toBe(true);
    }

    const notices = readFileSync(join(fontDirectory, "FONT-NOTICES.md"), "utf8");
    const pixelifyLicense = readFileSync(join(fontDirectory, "PixelifySans-OFL.txt"), "utf8");
    const silkscreenLicense = readFileSync(join(fontDirectory, "Silkscreen-OFL.txt"), "utf8");

    expect(notices).toContain("https://github.com/eifetx/Pixelify-Sans");
    expect(notices).toContain("https://github.com/googlefonts/silkscreen");
    expect(notices).toContain("Copyright 2021 The Pixelify Sans Project Authors");
    expect(notices).toContain("Copyright 2001 The Silkscreen Project Authors");
    expect(pixelifyLicense).toContain("Copyright 2021 The Pixelify Sans Project Authors");
    expect(silkscreenLicense).toContain("Copyright 2001 The Silkscreen Project Authors");
    expect(pixelifyLicense).toContain("SIL OPEN FONT LICENSE Version 1.1");
    expect(silkscreenLicense).toContain("SIL OPEN FONT LICENSE Version 1.1");
  });

  it("uses Pixelify for shared headings and square tokens for shared controls", () => {
    const radiusValuesFor = (className: string) => [...stylesheet.matchAll(new RegExp(`\\.${className}\\{[^}]*border-radius:\\s*([^;}]+)`, "g"))]
      .map((match) => match[1].trim());

    expect(stylesheet).toMatch(/h1,h2,h3\s*\{[^}]*font-family:\s*var\(--font-display\)/);
    expect(stylesheet).toMatch(/\.page-header h1\s*\{[^}]*font-family:\s*var\(--font-display\)/);
    expect(stylesheet).toMatch(/\.section-heading h2,\.section-block h2\s*\{[^}]*font-family:\s*var\(--font-display\)/);
    expect(radiusValuesFor("button").length).toBeGreaterThan(0);
    expect(radiusValuesFor("button")).toEqual(Array.from({ length: radiusValuesFor("button").length }, () => "var(--radius-control)"));
    expect(radiusValuesFor("icon-button").length).toBeGreaterThan(0);
    expect(radiusValuesFor("icon-button")).toEqual(Array.from({ length: radiusValuesFor("icon-button").length }, () => "var(--radius-control)"));
  });

  it("keeps structural UI geometry square and muted ink distinct from body ink", () => {
    expect(tokenValue("muted")).toBe("var(--ink-muted)");
    expect(tokenValue("radius-panel")).toBe("var(--radius-control)");

    const tokenizedRadii: Array<[string, string]> = [
      [".workspace-context", "var(--radius-control)"],
      [".nav-link", "var(--radius-control)"],
      [".period-chip", "var(--radius-control)"],
      [".section-block", "var(--radius-control)"],
      [".stat-strip", "var(--radius-control)"],
      [".developer-quick-links a", "var(--radius-control)"],
      [".status-label", "var(--radius-control)"],
      [".runway-track", "var(--radius-control)"],
      [".developer-model-row", "var(--radius-control)"],
      ["select", "var(--radius-control)"],
      [".select-filter select", "var(--radius-control)"],
      [".portal-select-wrap select", "var(--radius-control)"],
      [".dialog-form select", "var(--radius-control)"],
      [".route-mapping-control select", "var(--radius-control)"],
      [".quickstart-model select", "var(--radius-control)"],
      [".provider-brand-heading", "var(--radius-control)"],
      [".model-group-toggle", "var(--radius-control)"],
      [".analytics-range select", "var(--radius-control)"],
      [".analytics-stat-strip", "var(--radius-control)"],
      [".analytics-chart-card", "var(--radius-panel)"],
      [".analytics-model-ranking", "var(--radius-panel)"],
    ];

    for (const [selector, token] of tokenizedRadii) {
      expect(lastBorderRadiusFor(selector, stylesheet), selector).toBe(token);
    }

    const legacyStylesheet = readFileSync(resolve(process.cwd(), "../app/static/style.css"), "utf8");
    expect(legacyStylesheet).not.toMatch(/border-radius\s*:\s*(?:0|4px|8px|16px|24px|999px)\b/);

    for (const selector of [".metrics article", ".key-modal", "select"]) {
      expect(lastBorderRadiusFor(selector, legacyStylesheet), `legacy ${selector}`).toBe("var(--radius-control)");
    }
  });
});
