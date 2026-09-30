import { readFileSync } from "node:fs";
import { describe, expect, it } from "vitest";

describe("pixel dashboard visual contract", () => {
  it("loads the dedicated OpenRouter-inspired override after the base styles", () => {
    const main = readFileSync("src/main.tsx", "utf8");

    expect(main).toContain('import "./ui/styles.css";');
    expect(main).toContain('import "./ui/pixel-dashboard.css";');
    expect(main.indexOf('./ui/pixel-dashboard.css')).toBeGreaterThan(main.indexOf('./ui/styles.css'));
  });

  it("pins the 1920px-first dark pixel dashboard tokens and sidebar geometry", () => {
    const css = readFileSync("src/ui/pixel-dashboard.css", "utf8");

    expect(css).toMatch(/--pixel-canvas:\s*#07101d/i);
    expect(css).toMatch(/--pixel-violet:\s*#7c4dff/i);
    expect(css).toMatch(/\.sidebar\s*\{[\s\S]*?width:\s*272px/i);
    expect(css).toMatch(/\.main-content\s*\{[\s\S]*?max-width:\s*none/i);
    expect(css).toContain("@media (max-width: 1279px)");
  });

  it("shows the AI router identity and allowance summary in the sidebar", () => {
    const sidebar = readFileSync("src/ui/shell/Sidebar.tsx", "utf8");

    expect(sidebar).toContain("AI ROUTER");
    expect(sidebar).toContain("AllowancePill");
    expect(sidebar).toContain("Monthly usage");
  });
});
