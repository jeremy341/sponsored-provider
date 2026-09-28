import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { PixelIcon } from "./icons/PixelIcon";
import type { PixelIconName } from "./icons/pixelIconData";

const styles = readFileSync(resolve(process.cwd(), "src/ui/styles.css"), "utf8");

describe("PixelIcon", () => {
  it("renders the pixel grid with the canonical viewBox and CSS crisp-edge rule", () => {
    const { container } = render(<PixelIcon name="dashboard" />);
    const svg = container.querySelector("svg");

    expect(svg).toHaveAttribute("viewBox", "0 0 8 8");
    expect(svg).toHaveClass("pixel-icon-svg");
    expect(styles).toMatch(/\.pixel-icon-svg\s*\{\s*shape-rendering:\s*crispEdges;\s*\}/);
    expect(svg?.querySelectorAll("rect").length).toBeGreaterThan(0);
  });

  it("hides decorative icons from the accessibility tree by default", () => {
    const { container } = render(<PixelIcon name="search" />);
    const svg = container.querySelector("svg");

    expect(svg).toHaveAttribute("aria-hidden", "true");
    expect(svg).not.toHaveAttribute("role", "img");
    expect(screen.queryByRole("img")).not.toBeInTheDocument();
  });

  it("exposes a meaningful icon with its required accessible label", () => {
    render(<PixelIcon name="shield" decorative={false} label="Security safeguards" />);

    expect(screen.getByRole("img", { name: "Security safeguards" })).toHaveAttribute("viewBox", "0 0 8 8");
  });

  it("fails safely without rendering for an unknown runtime glyph name", () => {
    const unknownName = "not-a-glyph";
    // SAFETY: Bypass the static union to exercise untyped runtime callers.
    const { container } = render(<PixelIcon name={unknownName as PixelIconName} />);

    expect(container.querySelector("svg")).toBeNull();
  });
});
