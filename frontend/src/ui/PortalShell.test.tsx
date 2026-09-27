import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it } from "vitest";
import { App } from "./App";

afterEach(() => window.history.replaceState({}, "", "/"));

describe("portal shell", () => {
  it("shows developer-only navigation in the shared header", () => {
    window.history.replaceState({}, "", "/developer/keys?preview=developer");
    render(<App />);

    const navigation = screen.getByRole("navigation", { name: "Primary navigation" });

    expect(within(navigation).getByRole("link", { name: /API keys/i })).toHaveAttribute("aria-current", "page");
    expect(within(navigation).getByRole("link", { name: "Models" })).toBeInTheDocument();
    expect(within(navigation).queryByRole("link", { name: /People & keys/i })).not.toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Skip to content" })).toHaveAttribute("href", "#main-content");
  });

  it("keeps operator navigation separate and opens the mobile navigation with an accessible trigger", async () => {
    window.history.replaceState({}, "", "/operator?preview=operator");
    render(<App />);

    const navigation = screen.getByRole("navigation", { name: "Primary navigation" });

    expect(within(navigation).getByRole("link", { name: "People & keys" })).toBeInTheDocument();
    expect(within(navigation).queryByRole("link", { name: "API keys" })).not.toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Open navigation" }));
    expect(await screen.findByRole("dialog", { name: "Navigation" })).toBeInTheDocument();
  });
});
