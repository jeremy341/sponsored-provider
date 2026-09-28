import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes, useLocation } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";
import { api } from "../lib/api";
import { AuthPage } from "./AuthPage";

function Location() {
  const location = useLocation();

  return <output aria-label="Current location">{location.pathname}</output>;
}

function renderAuth() {
  return render(<MemoryRouter initialEntries={["/auth/login"]}><Routes><Route path="/auth/login" element={<AuthPage />} /><Route path="/developer" element={<Location />} /><Route path="/operator" element={<Location />} /></Routes></MemoryRouter>);
}

afterEach(() => {
  window.history.replaceState({}, "", "/");
  vi.restoreAllMocks();
});

describe("local auth", () => {
  it("uses decorative pixel icons for the auth brand, lock, and password reveal", () => {
    renderAuth();

    const icons = document.querySelectorAll("svg.pixel-icon-svg");

    expect(icons).toHaveLength(3);

    for (const icon of icons) expect(icon).toHaveAttribute("aria-hidden", "true");
    expect(screen.getByRole("button", { name: "Show password" }).querySelector("svg.pixel-icon-svg")).toHaveAttribute("aria-hidden", "true");
  });

  it("keeps account creation unavailable until an invite is present", async () => {
    renderAuth();

    await userEvent.click(screen.getByRole("button", { name: "Switch to account creation" }));

    expect(screen.getByText(/invitation link is required/i)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Create account" })).toBeDisabled();
  });

  it("offers accessible local login without an HCA control and uses generic credential errors", async () => {
    vi.spyOn(api, "localLogin").mockRejectedValue(new Error("bad credentials"));
    renderAuth();

    expect(screen.getByLabelText("Username")).toHaveAttribute("autocomplete", "username");
    expect(screen.getByLabelText("Password")).toHaveAttribute("autocomplete", "current-password");
    expect(screen.queryByText(/hack club|hca/i)).not.toBeInTheDocument();
    await userEvent.type(screen.getByLabelText("Username"), "person");
    await userEvent.type(screen.getByLabelText("Password"), "wrong-password");
    await userEvent.click(screen.getByRole("button", { name: "Sign in" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("Invalid username or password");
  });

  it("keeps account creation gated when no invite is present", async () => {
    renderAuth();

    await userEvent.click(screen.getByRole("button", { name: "Switch to account creation" }));

    expect(screen.getByText(/invitation link is required/i)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Create account" })).toBeDisabled();
  });

  it("sends only the fragment invite in the signup body, clears it, and routes by role", async () => {
    window.history.replaceState({}, "", "/auth/login?invite=query-secret#invite=fragment-secret");
    const signup = vi.spyOn(api, "localSignup").mockResolvedValue({ role: "operator" });
    renderAuth();

    await userEvent.type(screen.getByLabelText("Username"), "new operator");
    await userEvent.type(screen.getByLabelText("Password"), "correct horse battery staple");
    await userEvent.click(screen.getByRole("button", { name: "Create account" }));
    await waitFor(() => expect(signup).toHaveBeenCalledWith({ username: "new operator", password: "correct horse battery staple", invite: "fragment-secret" }));
    await waitFor(() => expect(screen.getByLabelText("Current location")).toHaveTextContent("/operator"));
    expect(window.location.hash).toBe("");
    expect(window.location.search).toContain("invite=query-secret");
  });

  it("reveals the password through a keyboard reachable control", async () => {
    renderAuth();
    const password = screen.getByLabelText("Password");
    expect(password).toHaveAttribute("type", "password");
    fireEvent.click(screen.getByRole("button", { name: "Show password" }));
    expect(password).toHaveAttribute("type", "text");
  });
});
