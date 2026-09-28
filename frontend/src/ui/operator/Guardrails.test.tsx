import { afterEach, describe, expect, it, vi } from "vitest";
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { App } from "../App";
import { api } from "../../lib/api";

afterEach(() => {
  vi.restoreAllMocks();
  window.history.replaceState({}, "", "/");
});

describe("operator guardrails", () => {
  it("rejects malformed IPs locally without calling the block API", async () => {
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
    const blockIp = vi.spyOn(api, "blockIp").mockResolvedValue(undefined);

    render(<App />);
    await screen.findByRole("button", { name: "Block IP" });

    await userEvent.type(screen.getByLabelText("IP address"), "not-an-ip");
    await userEvent.click(screen.getByRole("button", { name: "Block IP" }));

    const alert = await screen.findByRole("alert");

    expect(alert).toHaveTextContent(/valid IPv4 or IPv6 address/i);
    expect(blockIp).not.toHaveBeenCalled();
  });

  it("keeps the emergency-stop confirmation", async () => {
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

    render(<App />);

    const stopButton = await screen.findByRole("button", { name: "Stop gateway" });
    await userEvent.click(stopButton);

    const dialog = await screen.findByRole("dialog", { name: "Stop all new gateway requests now?" });

    expect(setGlobalStop).not.toHaveBeenCalled();

    await userEvent.click(within(dialog).getByRole("button", { name: "Cancel" }));
    await waitFor(() => expect(screen.queryByRole("dialog", { name: "Stop all new gateway requests now?" })).not.toBeInTheDocument());
    expect(setGlobalStop).not.toHaveBeenCalled();

    await userEvent.click(await screen.findByRole("button", { name: "Stop gateway" }));
    const confirmDialog = await screen.findByRole("dialog", { name: "Stop all new gateway requests now?" });
    await userEvent.click(within(confirmDialog).getByRole("button", { name: "Stop gateway" }));
    await waitFor(() => expect(setGlobalStop).toHaveBeenCalledWith(true));
  });
});
