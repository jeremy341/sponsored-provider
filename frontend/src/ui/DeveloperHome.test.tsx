import { render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";
import { App } from "./App";

afterEach(() => window.history.replaceState({}, "", "/"));

describe("developer home", () => {
  it("puts the personal allowance and first-call path ahead of empty usage", () => {
    window.history.replaceState({}, "", "/developer?preview=developer");
    render(<App />);

    expect(screen.getByRole("heading", { name: "Home" })).toBeInTheDocument();
    expect(screen.getAllByRole("link", { name: /quickstart/i }).some((link) => link.getAttribute("href") === "/developer/quickstart")).toBe(true);
    expect(screen.getAllByRole("link", { name: /models/i }).some((link) => link.getAttribute("href") === "/developer/models")).toBe(true);
    expect(screen.getByText(/no usage, keys, or models are shown/i)).toBeInTheDocument();
    expect(screen.queryByText(/\$7\.00/)).not.toBeInTheDocument();
    expect(screen.getByRole("link", { name: /view activity/i }).querySelector("svg.pixel-icon-svg")).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "No keys yet" }).closest(".empty-state")?.querySelector("svg.pixel-icon-svg")).toBeInTheDocument();
  });

  it("uses the pixel icon system for developer quickstart links", () => {
    window.history.replaceState({}, "", "/developer/quickstart?preview=developer");
    render(<App />);

    for (const label of ["Open API keys", "Browse models", "API documentation"]) {
      expect(screen.getByRole("link", { name: label }).querySelector("svg.pixel-icon-svg")).toBeInTheDocument();
    }
  });
});
