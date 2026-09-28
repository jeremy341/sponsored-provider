import { render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { App } from "./App";
import { api } from "../lib/api";

afterEach(() => {
  vi.restoreAllMocks();
  window.history.replaceState({}, "", "/");
});

function mockOperatorSession() {
  vi.spyOn(api, "getSession").mockResolvedValue({ user: { displayName: "Operator", email: null }, role: "operator", csrfToken: "csrf" });
}

function mockDeveloperSession() {
  vi.spyOn(api, "getSession").mockResolvedValue({ user: { displayName: "Dev", email: null }, role: "developer", csrfToken: "csrf" });
}

describe("role routing", () => {
  it("redirects an operator who opens a developer-only route", async () => {
    mockOperatorSession();
    window.history.replaceState({}, "", "/developer/keys");
    render(<App />);

    await waitFor(() => expect(window.location.pathname).toBe("/operator"));
    expect(await screen.findByRole("navigation", { name: "Primary navigation" })).toHaveTextContent("People & keys");
  });

  it("redirects a developer who opens an operator-only route", async () => {
    mockDeveloperSession();
    window.history.replaceState({}, "", "/operator/people");
    render(<App />);

    await waitFor(() => expect(window.location.pathname).toBe("/developer"));
    expect(await screen.findByRole("navigation", { name: "Primary navigation" })).toHaveTextContent("API keys");
  });

  it("shows the not-found page instead of redirecting when an operator opens an unknown path", async () => {
    mockOperatorSession();
    window.history.replaceState({}, "", "/totally/unknown");
    render(<App />);

    expect(await screen.findByRole("heading", { name: /page not found/i })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /go to overview/i })).toHaveAttribute("href", "/operator");
    expect(screen.queryByRole("heading", { name: "Overview" })).not.toBeInTheDocument();
  });

  it("shows the not-found page inside the developer shell for unknown paths", async () => {
    mockDeveloperSession();
    window.history.replaceState({}, "", "/nowhere");
    render(<App />);

    expect(await screen.findByRole("heading", { name: /page not found/i })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /go to home/i })).toHaveAttribute("href", "/developer");
  });
});
