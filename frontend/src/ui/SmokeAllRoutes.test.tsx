import { render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { App } from "./App";
import { api } from "../lib/api";
import type {
  ActivityEvent, ApiKeyRecord, CatalogOfferRecord, DeveloperDashboard, DeveloperInviteStatus, GuardrailSnapshot,
  ModelRecord, OperatorDashboard, Page, PersonRecord, ProviderConnectionRecord,
} from "../contracts/api";

const event: ActivityEvent = {
  id: "event-1", requestId: "req-abc123", occurredAt: "2026-09-27T08:00:00Z", modelId: "acme::model-x",
  providerName: "Acme AI", keyLabel: "OpenCode", inputTokens: 120, outputTokens: 30, totalTokens: 150,
  estimatedCostUsd: "0.000123456", costSource: "gateway_estimate", tokenCompleteness: "complete",
  status: "success", errorCategory: null, latencyMs: 425, cachedTokens: 20,
};

const key: ApiKeyRecord = {
  id: "key-1", label: "OpenCode", prefix: "sp_sk_test", modelAccess: { mode: "all_approved" }, spendCapUsd: null,
  spendUsedUsd: null, spendPeriod: null, spendResetAt: null, rpmLimit: null, createdAt: "2026-09-27T00:00:00Z", lastUsedAt: null, status: "active",
};

const model: ModelRecord = {
  id: "acme::model-x", displayName: "Model X", providerName: "Acme AI", capabilities: ["text"],
  inputUsdPerMillion: "0.3", outputUsdPerMillion: "1.2", cacheUsdPerMillion: "0.05",
  pricingVerified: true, approved: true, available: true, syncedAt: "2026-09-27T08:00:00Z", activeRouteCount: 1,
};

const person: PersonRecord = {
  id: "person-1", displayName: "pixiedev", email: null, status: "active", allowanceUsd: "7", allowancePeriod: "monthly",
  rpmLimit: 30, usedUsd: "1.25", reservedUsd: "0.25", allowanceResetAt: "2026-10-01T00:00:00Z", keyCount: 2, requestCount: 4, lastActiveAt: null,
};

const connection: ProviderConnectionRecord = {
  id: "conn-1", brandId: "brand-1", brandSlug: "acme-ai", brandName: "Acme AI", connectionLabel: "EU primary",
  providerKind: "openai", baseUrlDisplay: "https://api.acme.example/v1", enabled: true, mappingStatus: "mapped",
  health: "healthy", lastSyncAt: "2026-09-27T08:00:00Z", discoveredModels: 12, approvedModels: 3,
  budget: { limitUsd: "10", period: "weekly", reserveUsd: "1", usedUsd: "2.5", reservedUsd: "0.25", remainingUsd: "7.25", resetAt: "2026-09-29T00:00:00Z" },
};

const offer: CatalogOfferRecord = {
  id: "offer:acme-ai:model-x", brandSlug: "acme-ai", brandName: "Acme AI", canonicalModelId: "acme::model-x",
  displayName: "Model X", capabilities: ["text"], approved: true, available: true,
  activePrice: { inputUsdPerMillion: "0.3", outputUsdPerMillion: "1.2", cachedInputUsdPerMillion: null, source: "verified" },
  pendingPrice: null, priceSuggestions: [],
  routes: [{ id: "route-1", connectionId: "conn-1", connectionLabel: "EU primary", upstreamModelId: "raw-x", order: 0, enabled: true, active: true, connectionEnabled: true, stale: false, reviewRequired: false, priceStatus: "matching" }],
};

const guardrails: GuardrailSnapshot = {
  globalSpendCapUsd: 25, globalSpendUsedUsd: 4.2, safetyReserveUsd: 2.5, globalStopped: false,
  blockedIps: [{ ip: "203.0.113.24", reason: "Observed request abuse", createdAt: "2026-09-27T08:00:00Z" }],
  recentAudit: [{ id: "audit-1", actor: "operator", action: "ip.blocked", target: "203.0.113.24", occurredAt: "2026-09-27T08:00:00Z" }],
};

const analytics = {
  period: { key: "current_month" as const, from: "2026-09-01T00:00:00+02:00", to: "2026-09-28T10:00:00+02:00", timezone: "Europe/Berlin" as const },
  summary: null,
  series: [{ day: "2026-09-02", requests: 2, totalTokens: 10, estimatedSpendUsd: "0.5", unpricedRequests: 0 }],
  topModels: [{ modelId: "acme::model-x", providerName: "Acme AI", requests: 7, totalTokens: 140, estimatedSpendUsd: "0.12" }],
  modelSpend: [{ id: "offer:acme-ai:model-x", modelId: "acme::model-x", providerName: "Acme AI", requests: 7, totalTokens: 140, spendUsd: "0.12" }],
  knownSpendUsd: "0.12",
  unpricedRequests: 0,
};

const developerDashboard: DeveloperDashboard = {
  usage: { requests: 9, successfulRequests: 8, rejectedRequests: 1, inputTokens: 1000, outputTokens: 500, totalTokens: 1500, estimatedSpendUsd: "0.045", allowanceUsedUsd: 1.25, allowanceLimitUsd: 7, p95LatencyMs: 420, sampleCount: 9, period: "all time", source: "gateway_estimate" },
  series: [],
  topModels: [{ modelId: "acme::model-x", providerName: "Acme AI", requests: 9, totalTokens: 1500, estimatedSpendUsd: "0.045" }],
  keys: [key],
  recentActivity: [event],
  allowance: { usedUsd: "1.25", reservedUsd: "0.25", consumedUsd: "1.5", limitUsd: "7", remainingUsd: "5.5", period: "monthly", resetAt: "2026-10-01T00:00:00Z", source: "gateway estimate and active reservations" },
  analytics,
};

const operatorDashboard: OperatorDashboard = {
  usage: { requests: 42, successfulRequests: 40, rejectedRequests: 2, inputTokens: 9000, outputTokens: 4000, totalTokens: 13000, estimatedSpendUsd: "0.9", allowanceUsedUsd: null, allowanceLimitUsd: null, p95LatencyMs: 380, sampleCount: 42, period: "all time", source: "gateway_estimate" },
  series: [],
  topModels: [{ modelId: "acme::model-x", providerName: "Acme AI", requests: 42, totalTokens: 13000, estimatedSpendUsd: "0.9" }],
  providers: [],
  recentActivity: [event],
  guardrails,
  analytics,
};

const page = <T,>(items: T[]): Page<T> => ({ items, nextCursor: null });

function mockDeveloperApi() {
  vi.spyOn(api, "getSession").mockResolvedValue({ user: { displayName: "pixiedev", email: null }, role: "developer", csrfToken: "csrf" });
  vi.spyOn(api, "getDeveloperDashboard").mockResolvedValue(developerDashboard);
  vi.spyOn(api, "listModels").mockResolvedValue([model]);
  vi.spyOn(api, "listKeys").mockResolvedValue([key]);
  vi.spyOn(api, "listActivity").mockResolvedValue(page([event]));
  vi.spyOn(api, "getDeveloperInvites").mockResolvedValue({ entitled: true, can_issue: true, issued_at: null, invite: null } satisfies DeveloperInviteStatus);
}

function mockOperatorApi() {
  vi.spyOn(api, "getSession").mockResolvedValue({ user: { displayName: "operator", email: null }, role: "operator", csrfToken: "csrf" });
  vi.spyOn(api, "getOperatorDashboard").mockResolvedValue(operatorDashboard);
  vi.spyOn(api, "listModels").mockResolvedValue([model]);
  vi.spyOn(api, "listPeople").mockResolvedValue([person]);
  vi.spyOn(api, "listProviders").mockResolvedValue([connection]);
  vi.spyOn(api, "listOperatorOffers").mockResolvedValue([offer]);
  vi.spyOn(api, "listOperatorModels").mockResolvedValue([model]);
  vi.spyOn(api, "listOperatorActivity").mockResolvedValue(page([event]));
  vi.spyOn(api, "listOperatorInvites").mockResolvedValue([]);
  vi.spyOn(api, "getGuardrails").mockResolvedValue(guardrails);
}

const developerRoutes = ["/developer", "/developer/keys", "/developer/models", "/developer/activity", "/developer/analytics", "/developer/quickstart"];
const operatorRoutes = ["/operator", "/operator/people", "/operator/providers", "/operator/models", "/operator/usage", "/operator/guardrails", "/operator/audit"];

describe("portal route smoke", () => {
  const consoleErrors: unknown[] = [];
  const originalError = console.error;

  afterEach(() => {
    console.error = originalError;
    vi.restoreAllMocks();
    window.history.replaceState({}, "", "/");
    expect(consoleErrors).toEqual([]);
    consoleErrors.length = 0;
  });

  for (const route of developerRoutes) {
    it(`renders developer ${route} without console errors`, async () => {
      mockDeveloperApi();
      console.error = (...args: unknown[]) => { consoleErrors.push(args); };
      window.history.replaceState({}, "", route);
      render(<App />);

      await waitFor(() => expect(screen.getByRole("navigation", { name: "Primary navigation" })).toBeInTheDocument());
      await waitFor(() => expect(document.querySelector(".loading-line")).toBeNull());
    });
  }

  for (const route of operatorRoutes) {
    it(`renders operator ${route} without console errors`, async () => {
      mockOperatorApi();
      console.error = (...args: unknown[]) => { consoleErrors.push(args); };
      window.history.replaceState({}, "", route);
      render(<App />);

      await waitFor(() => expect(screen.getByRole("navigation", { name: "Primary navigation" })).toBeInTheDocument());
      await waitFor(() => expect(document.querySelector(".loading-line")).toBeNull());
    });
  }

  it("renders the developer model detail route without console errors", async () => {
    mockDeveloperApi();
    console.error = (...args: unknown[]) => { consoleErrors.push(args); };
    window.history.replaceState({}, "", "/developer/models/acme%3A%3Amodel-x");
    render(<App />);

    expect(await screen.findByRole("heading", { name: "Model X" })).toBeInTheDocument();
    await waitFor(() => expect(document.querySelector(".loading-line")).toBeNull());
  });
});
