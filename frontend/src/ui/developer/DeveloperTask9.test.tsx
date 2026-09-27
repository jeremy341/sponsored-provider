import { describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import type { ActivityEvent, ModelRecord, PortalApi } from "../../contracts/api";
import { AllowanceSummary } from "./AllowanceSummary";
import { ModelCatalogPage } from "./ModelCatalogPage";
import { DeveloperActivityPage } from "./DeveloperActivityPage";
import { ModelAccessPicker } from "./ModelAccessPicker";

const model: ModelRecord = {
  id: "acme::model-x", displayName: "Model X", upstreamModelId: "private/raw-model-x", providerId: "private-connection-id", providerName: "Acme AI",
  capabilities: ["text", "vision"], inputUsdPerMillion: "0.3", outputUsdPerMillion: "1.2", cacheUsdPerMillion: "0.05",
  pricingVerified: true, priceSource: "Models.dev · verified", approved: true, available: true, syncedAt: "2026-09-27T08:00:00Z",
};

const event: ActivityEvent = {
  id: "event-1", requestId: "req-abc123", occurredAt: "2026-09-27T08:00:00Z", modelId: "acme::model-x",
  providerName: "Acme AI", keyLabel: "OpenCode", inputTokens: 120, outputTokens: 30, totalTokens: 150,
  estimatedCostUsd: "0.000123456", costSource: "gateway_estimate", tokenCompleteness: "complete",
  status: "success", errorCategory: null, latencyMs: 425, cachedTokens: 20,
};

function api(overrides: Partial<PortalApi> = {}): PortalApi {
  const mock = {
    listModels: vi.fn().mockResolvedValue([model]),
    listActivity: vi.fn().mockResolvedValue({ items: [event], nextCursor: null }),
    listKeys: vi.fn().mockResolvedValue([]),
    ...overrides,
  };

  // SAFETY: these component tests invoke only listModels, listActivity, and listKeys; all are supplied above.
  return mock as PortalApi;
}

describe("Task 9 developer views", () => {
  it("shows the shared allowance, reservations, remaining balance, and Berlin reset", () => {
    render(<AllowanceSummary allowance={{ usedUsd: "1.234567891", reservedUsd: "0.25", consumedUsd: "1.484567891", limitUsd: "5", remainingUsd: "3.515432109", period: "weekly", resetAt: "2026-09-28T00:00:00Z", source: "gateway estimate and active reservations" }} />);
    expect(screen.getByText("$1.234567891")).toBeInTheDocument();
    expect(screen.getByText("$0.25")).toBeInTheDocument();
    expect(screen.getByText("$3.515432109")).toBeInTheDocument();
    expect(screen.getByText(/Monday, 28 September 2026.*Berlin/i)).toBeInTheDocument();
  });

  it("does not turn an unknown allowance into zero or a fake reset", () => {
    render(<AllowanceSummary allowance={null} />);
    expect(screen.getByText(/Allowance has not been assigned/i)).toBeInTheDocument();
    expect(screen.queryByText("$0.00")).not.toBeInTheDocument();
  });

  it("groups the public catalog by provider and shows exact input/output USD rates", async () => {
    render(<ModelCatalogPage portalApi={api()} />);
    expect(await screen.findByRole("heading", { name: "Acme AI" })).toBeInTheDocument();
    expect(screen.getByText("$0.30 / 1M input")).toBeInTheDocument();
    expect(screen.getByText("$1.20 / 1M output")).toBeInTheDocument();
  });

  it("shows a model detail with only verified cache price and public OpenAI example", async () => {
    render(<ModelCatalogPage portalApi={api()} />);
    await userEvent.click(await screen.findByRole("button", { name: /View details for Acme AI \/ Model X/i }));
    expect(screen.getByText("Cached input")).toBeInTheDocument();
    expect(screen.getByText("$0.05")).toBeInTheDocument();
    expect(screen.getByText("acme::model-x", { selector: "code" })).toBeInTheDocument();
    expect(screen.getByText(/"model":\s*"acme::model-x"/)).toBeInTheDocument();
    expect(screen.queryByText(/context window/i)).not.toBeInTheDocument();
    expect(screen.queryByText("private/raw-model-x")).not.toBeInTheDocument();
    expect(screen.queryByText("private-connection-id")).not.toBeInTheDocument();
  });

  it("omits unknown cached-input prices instead of implying they are free", async () => {
    render(<ModelCatalogPage portalApi={api({ listModels: vi.fn().mockResolvedValue([{ ...model, cacheUsdPerMillion: null }]) })} />);
    await userEvent.click(await screen.findByRole("button", { name: /View details for Acme AI \/ Model X/i }));
    expect(screen.queryByText(/cached input/i)).not.toBeInTheDocument();
  });

  it("shows an honest empty catalog in preview mode without API errors", async () => {
    window.history.replaceState({}, "", "/developer/models?preview=developer");
    const listModels = vi.fn();
    render(<ModelCatalogPage portalApi={api({ listModels })} />);
    expect(await screen.findByText("No published models yet")).toBeInTheDocument();
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
    expect(listModels).not.toHaveBeenCalled();
    window.history.replaceState({}, "", "/");
  });

  it("does not display a cached-input rate unless pricing is verified", async () => {
    render(<ModelCatalogPage portalApi={api({ listModels: vi.fn().mockResolvedValue([{ ...model, pricingVerified: false }]) })} />);
    await userEvent.click(await screen.findByRole("button", { name: /View details for Acme AI \/ Model X/i }));
    expect(screen.queryByText("Cached input")).not.toBeInTheDocument();
  });

  it("shows only safe request facts and renders unknown tokens as not reported", async () => {
    render(<DeveloperActivityPage portalApi={api({ listActivity: vi.fn().mockResolvedValue({ items: [{ ...event, inputTokens: null, outputTokens: null, totalTokens: null, tokenCompleteness: "unknown", requestIp: "198.51.100.8" }], nextCursor: null }) })} />);
    expect(await screen.findByText("req-abc123")).toBeInTheDocument();
    expect(screen.getAllByText(/Not reported/i).length).toBeGreaterThan(0);
    expect(screen.queryByText("198.51.100.8")).not.toBeInTheDocument();
    expect(screen.queryByText(/the actual prompt body|the generated completion body/i)).not.toBeInTheDocument();
  });

  it("defaults a new key to all published models and exposes the selected-model mode", async () => {
    const onModeChange = vi.fn();
    const onSelectedChange = vi.fn();
    render(<ModelAccessPicker models={[model]} mode="all_approved" selectedModelIds={[]} onModeChange={onModeChange} onSelectedChange={onSelectedChange} />);
    expect(screen.getByRole("radio", { name: /All published models/i })).toBeChecked();
    await userEvent.click(screen.getByRole("radio", { name: /Choose specific models/i }));
    expect(onModeChange).toHaveBeenCalledWith("selected");
  });

  it("keeps selected key access on stable public model IDs", async () => {
    const onSelectedChange = vi.fn();
    render(<ModelAccessPicker models={[model]} mode="selected" selectedModelIds={[]} onModeChange={vi.fn()} onSelectedChange={onSelectedChange} />);
    expect(screen.getByRole("group", { name: "Acme AI" })).toBeInTheDocument();
    await userEvent.click(screen.getByRole("checkbox", { name: /acme::model-x/i }));
    expect(onSelectedChange).toHaveBeenCalledWith(["acme::model-x"]);
    expect(screen.queryByLabelText(/private\/raw-model-x/i)).not.toBeInTheDocument();
  });
});
