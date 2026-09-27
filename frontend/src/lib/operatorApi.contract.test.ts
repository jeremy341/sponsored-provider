import { afterEach, describe, expect, it, vi } from "vitest";
import { api } from "./api";

afterEach(() => vi.unstubAllGlobals());

function stubResponse(bodyJson = "{}", status = 200) {
  const fetchMock = vi.fn().mockResolvedValue(new Response(status === 204 ? null : bodyJson, {
    status,
    headers: status === 204 ? undefined : { "Content-Type": "application/json" },
  }));

  vi.stubGlobal("fetch", fetchMock);

  return fetchMock;
}

describe("operator provider API contracts", () => {
  it("uses the backend create and discovery response shapes", async () => {
    const payload = { id: "connection-1", name: "Acme", brandSlug: "acme", connectionLabel: "EU", models: ["model-a"] };
    const fetchMock = stubResponse(JSON.stringify(payload), 201);
    const created = await api.createProvider({ name: "Acme", brandSlug: "acme", connectionLabel: "EU", baseUrl: "https://api.example.test/v1", apiKey: "secret" });
    expect(created).toEqual(payload);
    expect(JSON.parse(String(fetchMock.mock.calls[0][1].body))).toMatchObject({ apiKey: "secret" });

    const synced = { providerId: "profile-1", connectionId: "connection-1", modelsDiscovered: 2, models: ["model-a", "model-b"], staleModels: 0 };
    stubResponse(JSON.stringify(synced));
    await expect(api.syncProvider("connection-1")).resolves.toEqual(synced);
  });

  it("posts decimal price suggestions, approves the returned version, and sends exact routing controls", async () => {
    const fetchMock = stubResponse(JSON.stringify({ id: "price-1", offerId: "offer-1", status: "pending" }), 201);
    await expect(api.updateOfferPrice("offer-1", {
      inputUsdPerMillion: "0.125", outputUsdPerMillion: "0.75", cachedInputUsdPerMillion: "0.02", source: "Models.dev", effectiveAt: null,
    })).resolves.toEqual({ id: "price-1", offerId: "offer-1", status: "pending" });
    expect(fetchMock.mock.calls[0][1].method).toBe("PATCH");
    expect(JSON.parse(String(fetchMock.mock.calls[0][1].body))).toEqual({
      inputUsdPerMillion: "0.125", outputUsdPerMillion: "0.75", cachedInputUsdPerMillion: "0.02", source: "Models.dev",
    });

    const calls = stubResponse("{}", 204);
    await api.approveOfferPrice("offer-1", "price-1");
    await api.setOfferAvailable("offer-1", false);
    await api.updateRouteOrder("offer-1", ["connection-2", "connection-1"]);
    await api.mapConnectionModel("connection-1", "raw/model", "offer-1");
    await api.updateConnectionBudget("connection-1", { limitUsd: "20.000000001", period: "weekly", reserveUsd: "1.25" });

    expect(calls.mock.calls.map(([url, init]) => [url, init.method, init.body && JSON.parse(String(init.body))])).toEqual([
      ["/api/operator/offers/offer-1/prices/price-1/approve", "POST", undefined],
      ["/api/operator/offers/offer-1/availability", "PATCH", { enabled: false }],
      ["/api/operator/offers/offer-1/routes", "PATCH", { connectionIds: ["connection-2", "connection-1"] }],
      ["/api/operator/connections/connection-1/models/mapping", "PATCH", { upstreamModelId: "raw/model", offerId: "offer-1" }],
      ["/api/operator/connections/connection-1/budget", "POST", { limitUsd: "20.000000001", period: "weekly", reserveUsd: "1.25" }],
    ]);
  });
});
