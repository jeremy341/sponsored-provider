import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it, vi } from "vitest";
import type { ModelRecord, PortalApi } from "../../contracts/api";
import { ModelCatalogPage } from "./ModelCatalogPage";

const baseModel: ModelRecord = {
  id: "nimbus::deepseek/v4-flash",
  displayName: "DeepSeek V4 Flash",
  providerName: "Nimbus",
  capabilities: ["text"],
  inputUsdPerMillion: "0.3",
  outputUsdPerMillion: "1.2",
  cacheUsdPerMillion: null,
  pricingVerified: true,
  priceSource: "Models.dev",
  approved: true,
  available: true,
  syncedAt: null,
  activeRouteCount: null,
};

function portalApi(models: ModelRecord[]): Pick<PortalApi, "listModels"> {
  return { listModels: vi.fn().mockResolvedValue(models) };
}

describe("provider model catalog", () => {
  it("renders offers as provider-grouped cards with public price and route count", async () => {
    const models = [
      { ...baseModel, activeRouteCount: 2 },
      { ...baseModel, id: "openrouter::deepseek/v4-flash", providerName: "OpenRouter" },
    ];

    render(<MemoryRouter><ModelCatalogPage portalApi={portalApi(models)} /></MemoryRouter>);

    const nimbus = await screen.findByRole("region", { name: "Nimbus models" });
    expect(within(nimbus).getByRole("link", { name: /DeepSeek V4 Flash/ })).toHaveAttribute("href", "/developer/models/nimbus%3A%3Adeepseek%2Fv4-flash");
    expect(within(nimbus).getByText("2 active routes")).toBeInTheDocument();
    expect(screen.getByRole("region", { name: "OpenRouter models" })).toBeInTheDocument();
    expect(screen.getAllByText("$0.30")).toHaveLength(2);
  });

  it("keeps the copy-ID action independent from the detail link and preserves catalog filters", async () => {
    window.history.replaceState({}, "", "/developer/models?search=deepseek&capability=text");
    Object.defineProperty(navigator, "clipboard", { configurable: true, value: { writeText: vi.fn().mockResolvedValue(undefined) } });
    render(<MemoryRouter initialEntries={["/developer/models?search=deepseek&capability=text"]}><ModelCatalogPage portalApi={portalApi([baseModel])} /></MemoryRouter>);

    const card = await screen.findByRole("article", { name: /DeepSeek V4 Flash/ });
    expect(within(card).getByRole("link", { name: /DeepSeek V4 Flash/ })).toBeInTheDocument();
    expect(within(card).getByRole("button", { name: /copy model id/i }).querySelector("svg.lucide")).toHaveAttribute("aria-hidden", "true");
    await userEvent.click(within(card).getByRole("button", { name: /copy model id/i }));
    expect(navigator.clipboard.writeText).toHaveBeenCalledWith(baseModel.id);
    expect(within(card).getByRole("link", { name: /DeepSeek V4 Flash/ })).toHaveAttribute("href", expect.stringContaining("search=deepseek"));
  });
});
