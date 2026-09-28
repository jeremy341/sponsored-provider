import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { describe, expect, it, vi } from "vitest";
import type { ModelRecord, PortalApi } from "../../contracts/api";
import { ModelDetailPage } from "./ModelDetailPage";

const model: ModelRecord = {
  id: "nimbus::deepseek/v4-flash",
  displayName: "DeepSeek V4 Flash",
  providerName: "Nimbus",
  capabilities: ["text"],
  inputUsdPerMillion: "0.3",
  outputUsdPerMillion: "1.2",
  cacheUsdPerMillion: "0.08",
  pricingVerified: true,
  priceSource: "Models.dev",
  approved: true,
  available: true,
  syncedAt: null,
  activeRouteCount: null,
};

function api(models: ModelRecord[]): Pick<PortalApi, "listModels"> {
  return { listModels: vi.fn().mockResolvedValue(models) };
}

function renderDetails(entry: string, models: ModelRecord[]) {
  return render(<MemoryRouter initialEntries={[entry]}><Routes><Route path="/developer/models/*" element={<ModelDetailPage portalApi={api(models)} />} /></Routes></MemoryRouter>);
}

describe("model detail route", () => {
  it("resolves provider-scoped slash IDs, restores catalog state, and offers language tabs", async () => {
    renderDetails("/developer/models/nimbus%3A%3Adeepseek%2Fv4-flash?search=deepseek&capability=text", [model]);

    expect(await screen.findByRole("heading", { name: "DeepSeek V4 Flash" })).toBeInTheDocument();
    expect(screen.getByText("$0.30")).toBeInTheDocument();
    expect(screen.getByText("$1.20")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /back to models/i })).toHaveAttribute("href", "/developer/models?search=deepseek&capability=text");
    expect(screen.getByRole("tab", { name: "cURL" })).toHaveAttribute("aria-selected", "true");
    const curlCode = screen.getByText(/curl http:\/\/localhost:\d+\/v1\/chat\/completions/).textContent ?? "";
    expect(curlCode).toContain("\n  -H");
    expect(curlCode).not.toContain("\n+");
    await userEvent.click(screen.getByRole("tab", { name: "Python" }));
    expect(screen.getByText(/base_url="http:\/\/localhost:\d+\/v1"/)).toBeInTheDocument();
    expect(screen.getByText(/YOUR_API_KEY/)).toBeInTheDocument();
    expect(screen.queryByText(/private\/raw|connection-id|sk-[a-z]/i)).not.toBeInTheDocument();
  });

  it("shows an unavailable state for a stale or unpublished public ID", async () => {
    renderDetails("/developer/models/removed%3A%3Amodel%2Fgone", [model]);
    const state = await screen.findByRole("region", { name: /model unavailable/i });
    expect(within(state).getByText(/no longer in the published catalog/i)).toBeInTheDocument();
    expect(within(state).getByRole("link", { name: /back to models/i })).toHaveClass("model-back-link");
  });
});
