import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import type { CatalogOfferRecord, DeveloperDashboard, GuardrailSnapshot, ProviderConnectionRecord } from "../../contracts/api";
import { api } from "../../lib/api";
import { pickSelect } from "../../test/select";
import { DeveloperAnalyticsPage } from "../developer/DeveloperAnalyticsPage";
import { AuditLogPage } from "./AuditLogPage";
import { GuardrailsPage } from "./GuardrailsPage";
import { ModelsPricingPage } from "./models/ModelsPricingPage";
import { ProviderListPage } from "./providers/ProviderListPage";

const connection: ProviderConnectionRecord = {
  id: "conn-1", brandId: "brand-1", brandSlug: "acme", brandName: "Acme AI", connectionLabel: "EU primary",
  providerKind: "openai_compatible", baseUrlDisplay: "https://eu.example.test/v1", enabled: true,
  mappingStatus: "matched", health: "healthy", lastSyncAt: "2026-09-27T08:00:00Z", discoveredModels: 2,
  approvedModels: 1, budget: { limitUsd: "20", period: "weekly", reserveUsd: "2", usedUsd: "3", reservedUsd: "0.5", remainingUsd: "16.5", resetAt: null },
};

const offer: CatalogOfferRecord = {
  id: "offer-1", brandSlug: "acme", brandName: "Acme AI", canonicalModelId: "acme/model-x",
  displayName: "Model X", capabilities: ["text"], approved: true, available: true,
  activePrice: { inputUsdPerMillion: "1", outputUsdPerMillion: "2", cachedInputUsdPerMillion: null, source: "Provider price list" },
  pendingPrice: null, priceSuggestions: [],
  routes: [{ id: "route-1", connectionId: "conn-1", connectionLabel: "EU primary", upstreamModelId: "model-x", order: 0, enabled: true, active: true, connectionEnabled: true, stale: false, reviewRequired: false, priceStatus: "matching" }],
};

const audit: GuardrailSnapshot = {
  globalSpendCapUsd: null, globalSpendUsedUsd: null, safetyReserveUsd: null, globalStopped: false, blockedIps: [],
  recentAudit: [
    { id: "a-1", actor: "operator", action: "ip.blocked", target: "203.0.113.24", occurredAt: "2026-09-27T08:00:00Z" },
    { id: "a-2", actor: "operator", action: "offer.price_approved", target: "offer-1", occurredAt: "2026-09-27T09:00:00Z" },
  ],
};

const developerDashboard: DeveloperDashboard = {
  usage: null, series: [], topModels: [], keys: [], recentActivity: [], allowance: null,
  analytics: {
    period: { key: "current_month", from: "2026-09-01T00:00:00+02:00", to: "2026-09-28T10:00:00+02:00", timezone: "Europe/Berlin" as const },
    summary: null, series: [], topModels: [], modelSpend: [], knownSpendUsd: "0", unpricedRequests: 0,
  },
};

describe("operator page split", () => {
  it("providers page lists connections without the catalog section", async () => {
    render(<ProviderListPage portalApi={{ ...api, listProviders: vi.fn().mockResolvedValue([connection]), listOperatorOffers: vi.fn().mockResolvedValue([offer]) }} />);

    expect(await screen.findByText("EU primary")).toBeInTheDocument();
    expect(screen.queryByRole("heading", { name: "Catalog offers" })).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Add connection/i })).toBeInTheDocument();
  });

  it("models & pricing page groups catalog offers and opens the review sheet", async () => {
    render(<ModelsPricingPage portalApi={{ ...api, listProviders: vi.fn().mockResolvedValue([connection]), listOperatorOffers: vi.fn().mockResolvedValue([offer]) }} />);

    expect(await screen.findByRole("heading", { name: "Models & pricing" })).toBeInTheDocument();
    const brand = await screen.findByRole("button", { name: /Acme AI/ });
    if (brand.getAttribute("aria-expanded") !== "true") await userEvent.click(brand);
    await userEvent.click(await screen.findByRole("button", { name: "Model X" }));
    expect(await screen.findByRole("dialog", { name: "Model X" })).toBeInTheDocument();
    expect(screen.getByText(/Active price/i)).toBeInTheDocument();
  });

  it("audit log page renders recorded actions as a table", async () => {
    vi.spyOn(api, "getGuardrails").mockResolvedValue(audit);
    render(<AuditLogPage />);

    expect(await screen.findByRole("heading", { name: "Audit log" })).toBeInTheDocument();
    expect(await screen.findByText("ip.blocked")).toBeInTheDocument();
    expect(screen.getByText("offer.price_approved")).toBeInTheDocument();
    expect(screen.getByText("203.0.113.24")).toBeInTheDocument();
  });

  it("guardrails page keeps guardrail controls but no longer embeds the audit trail", async () => {
    render(<GuardrailsPage />);

    expect(await screen.findByRole("heading", { name: "Global gateway" })).toBeInTheDocument();
    expect(screen.queryByRole("heading", { name: /Recent audit events/i })).not.toBeInTheDocument();
    expect(screen.queryByText("ip.blocked")).not.toBeInTheDocument();
  });
});

describe("developer analytics tab", () => {
  it("renders the period analytics and re-queries when the range changes", async () => {
    const getDeveloperDashboard = vi.spyOn(api, "getDeveloperDashboard").mockResolvedValue(developerDashboard);
    render(<DeveloperAnalyticsPage />);

    expect(await screen.findByRole("heading", { name: "Usage analytics" })).toBeInTheDocument();
    expect(screen.getByRole("combobox", { name: /analytics period/i })).toHaveTextContent("This month");
    await pickSelect(/analytics period/i, "Last 7 days");
    await waitFor(() => expect(getDeveloperDashboard).toHaveBeenLastCalledWith("7d"));
  });
});
