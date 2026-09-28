import { afterEach, describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { App } from "../App";
import { api } from "../../lib/api";

afterEach(() => {
  vi.restoreAllMocks();
  window.history.replaceState({}, "", "/");
});

describe("operator guardrails", () => {
  it("keeps the emergency-stop confirmation and shows its pixel action glyph", async () => {
    window.history.replaceState({}, "", "/operator/guardrails");
    vi.spyOn(api, "getSession").mockResolvedValue({ user: { displayName: "Operator", email: null }, role: "operator", csrfToken: "csrf" });
    vi.spyOn(api, "getGuardrails").mockResolvedValue({
      globalSpendCapUsd: 20,
      globalSpendUsedUsd: 4,
      safetyReserveUsd: 2,
      globalStopped: false,
      blockedIps: [],
      recentAudit: [],
    });
    const setGlobalStop = vi.spyOn(api, "setGlobalStop").mockResolvedValue(undefined);
    const confirm = vi.spyOn(window, "confirm").mockReturnValue(false);

    render(<App />);

    const stopButton = await screen.findByRole("button", { name: "Stop gateway" });
    expect(stopButton.querySelector("svg.pixel-icon-svg")).toBeInTheDocument();
    await userEvent.click(stopButton);

    expect(confirm).toHaveBeenCalledWith("Stop all new gateway requests now? Active streams may finish.");
    expect(setGlobalStop).not.toHaveBeenCalled();
  });
});
