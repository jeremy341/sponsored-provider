import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it } from "vitest";
import { App } from "./App";

afterEach(() => window.history.replaceState({}, "", "/"));

describe("portal shell", () => {
  it("shows developer-only navigation in the sidebar rail", () => {
    window.history.replaceState({}, "", "/developer/keys?preview=developer");
    render(<App />);

    const navigation = screen.getByRole("navigation", { name: "Primary navigation" });
    const brands = screen.getAllByRole("link", { name: "provider." });
    const navLinks = within(navigation).getAllByRole("link");

    expect(within(navigation).getByRole("link", { name: /API keys/i })).toHaveAttribute("aria-current", "page");
    expect(within(navigation).getByRole("link", { name: "Models" })).toBeInTheDocument();
    expect(within(navigation).queryByRole("link", { name: /People & keys/i })).not.toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Skip to content" })).toHaveAttribute("href", "#main-content");

    expect(brands).toHaveLength(1);

    for (const brand of brands) expect(brand.querySelector("svg.lucide")).toBeInTheDocument();

    expect(navLinks).toHaveLength(5);

    for (const link of navLinks) expect(link.querySelector("svg.lucide")).toHaveAttribute("aria-hidden", "true");

    const previewIcon = document.querySelector("svg.lucide-circle-help");

    expect(previewIcon).toBeInTheDocument();
    expect(previewIcon).toHaveAttribute("aria-label", "Preview only");
  });

  it("keeps operator navigation separate and opens the mobile navigation with an accessible trigger", async () => {
    window.history.replaceState({}, "", "/operator?preview=operator");
    render(<App />);

    const navigation = screen.getByRole("navigation", { name: "Primary navigation" });

    expect(within(navigation).getByRole("link", { name: "People & keys" })).toBeInTheDocument();
    expect(within(navigation).queryByRole("link", { name: "API keys" })).not.toBeInTheDocument();

    const openNavigation = screen.getByRole("button", { name: "Open navigation" });

    await userEvent.click(openNavigation);
    const dialog = await screen.findByRole("dialog", { name: "Navigation" });

    expect(dialog.querySelectorAll("svg.lucide")).toHaveLength(7);

    await userEvent.keyboard("{Escape}");
    await waitFor(() => expect(screen.queryByRole("dialog", { name: "Navigation" })).not.toBeInTheDocument());
    expect(openNavigation).toHaveFocus();

    await userEvent.click(screen.getByRole("button", { name: "Open navigation" }));
    await screen.findByRole("dialog", { name: "Navigation" });
    await userEvent.selectOptions(screen.getByLabelText("Choose portal"), "developer");

    const developerNavigation = screen.getByRole("navigation", { name: "Primary navigation" });

    expect(await within(developerNavigation).findByRole("link", { name: "API keys" })).toBeInTheDocument();
    expect(within(developerNavigation).queryByRole("link", { name: "People & keys" })).not.toBeInTheDocument();
  });
});
