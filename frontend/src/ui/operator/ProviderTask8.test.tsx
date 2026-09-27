import { describe, expect, it, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { ProviderListPage } from "./providers/ProviderListPage";
import { ConnectionBudgetEditor } from "./providers/ConnectionBudgetEditor";
import { AllowanceEditor } from "./people/AllowanceEditor";
import { OperatorUsagePage } from "./usage/OperatorUsagePage";
import { formatUsd, ratioPercent } from "../../lib/money";
import { ApiError, api as portalApi } from "../../lib/api";
import type { CatalogOfferRecord, PersonRecord, PortalApi, ProviderConnectionRecord } from "../../contracts/api";

const connection: ProviderConnectionRecord = {
  id: "conn-1", brandId: "brand-1", brandSlug: "acme", brandName: "Acme AI", connectionLabel: "EU primary",
  providerKind: "openai_compatible", baseUrlDisplay: "https://eu.example.test/v1", enabled: true,
  mappingStatus: "matched", health: "healthy", lastSyncAt: "2026-09-27T08:00:00Z", discoveredModels: 2,
  approvedModels: 1, budget: { limitUsd: "20", period: "weekly", reserveUsd: "2", usedUsd: "3.125",
    reservedUsd: "0.5", remainingUsd: "16.375", resetAt: "2026-09-28T00:00:00Z" },
};

const offer: CatalogOfferRecord = {
  id: "offer-1", brandSlug: "acme", brandName: "Acme AI", canonicalModelId: "acme/model-x",
  displayName: "Model X", capabilities: ["text"], approved: true, available: true,
  activePrice: { inputUsdPerMillion: "1", outputUsdPerMillion: "2", cachedInputUsdPerMillion: null, source: "Provider price list", effectiveAt: "2026-09-20T00:00:00Z" },
  pendingPrice: { inputUsdPerMillion: "1.25", outputUsdPerMillion: "2.5", cachedInputUsdPerMillion: null, source: "Models.dev", effectiveAt: null },
  priceSuggestions: [], routes: [
    { id: "route-1", connectionId: connection.id, connectionLabel: connection.connectionLabel, upstreamModelId: "model-x-v2", order: 0, enabled: true, active: true, connectionEnabled: true, stale: false, reviewRequired: false, priceStatus: "matching" },
    { id: "route-2", connectionId: "conn-2", connectionLabel: "US fallback", upstreamModelId: "model-x", order: 1, enabled: false, active: false, connectionEnabled: true, stale: false, reviewRequired: true, priceStatus: "mismatch" },
  ],
};

const person: PersonRecord = {
  id: "user-1", displayName: "Ada", email: "ada@example.test", status: "active", allowanceUsd: "12.50",
  allowancePeriod: "weekly", usedUsd: "3.25", reservedUsd: "0.25", allowanceResetAt: "2026-09-28T00:00:00Z",
  rpmLimit: 30, keyCount: 2, requestCount: 14, lastActiveAt: null,
};

function api(overrides: Partial<PortalApi> = {}): PortalApi {
  const defaults: Partial<PortalApi> = {
    listProviders: vi.fn().mockResolvedValue([connection]), createProvider: vi.fn(), syncProvider: vi.fn(),
    listOperatorOffers: vi.fn().mockResolvedValue([offer]), updateOfferPrice: vi.fn(), approveOfferPrice: vi.fn(),
    setOfferAvailable: vi.fn(), setRouteAvailability: vi.fn().mockResolvedValue(undefined), updateRouteOrder: vi.fn(), mapConnectionModel: vi.fn(),
    updateConnectionBudget: vi.fn(), ...overrides,
  };

  return { ...portalApi, ...defaults, ...overrides };
}

async function openBrand(name = "Acme AI") {
  const brand = await screen.findByRole("button", { name: new RegExp(name) });

  if (brand.getAttribute("aria-expanded") !== "true") await userEvent.click(brand);
}

async function openOffer(name = "Model X") {
  const brand = await screen.findByRole("button", { name: /Acme AI/ });

  if (brand.getAttribute("aria-expanded") !== "true") await userEvent.click(brand);
  await userEvent.click(await screen.findByRole("button", { name: new RegExp(name) }));
}

describe("Task 8 operator interface", () => {
  it("renders_empty_provider_state", async () => {
    render(<ProviderListPage portalApi={api({ listProviders: vi.fn().mockResolvedValue([]), listOperatorOffers: vi.fn().mockResolvedValue([]) })} />);
    expect(await screen.findByText(/No provider connections/i)).toBeInTheDocument();
    expect(screen.getAllByRole("button", { name: /Add connection/i })).toHaveLength(2);
  });

  it("shows_sync_error_without_erasing_existing_models", async () => {
    const client = api({ syncProvider: vi.fn().mockRejectedValue(new Error("offline")) });
    render(<ProviderListPage portalApi={client} />);
    await openBrand();
    expect(await screen.findByText("Model X")).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: /Sync EU primary/i }));
    expect(await screen.findByRole("alert")).toHaveTextContent(/sync failed/i);
    expect(screen.getByText("Model X")).toBeInTheDocument();
  });

  it("creates_connection_once_and_clears_its_raw_secret", async () => {
    const createProvider = vi.fn().mockResolvedValue({
      id: connection.id, name: connection.brandName, brandSlug: connection.brandSlug,
      connectionLabel: connection.connectionLabel, models: ["model-x", "model-y"],
    });

    render(<ProviderListPage portalApi={api({ createProvider })} />);
    await userEvent.click((await screen.findAllByRole("button", { name: /Add connection/i }))[0]);
    await userEvent.type(screen.getByLabelText(/Provider brand/i), "Acme AI");
    await userEvent.type(screen.getByLabelText(/Private connection label/i), "EU primary");
    await userEvent.type(screen.getByLabelText(/OpenAI compatible HTTPS URL/i), "https://eu.example.test/v1");
    await userEvent.type(screen.getByLabelText(/Provider credential/i), "secret-once");
    await userEvent.click(screen.getByRole("button", { name: /Test & fetch models/i }));
    expect(await screen.findByText(/Connection test passed.*Discovery found 2 models/i)).toBeInTheDocument();
    expect(createProvider).toHaveBeenCalledTimes(1);
    expect(createProvider).toHaveBeenCalledWith(expect.objectContaining({ apiKey: "secret-once" }));
    await userEvent.click(screen.getByRole("button", { name: /Add connection/i }));
    expect(screen.getByLabelText(/Provider credential/i)).toHaveValue("");
  });

  it("reports_initial_discovery_failure_without_faking_a_second_sync", async () => {
    const createProvider = vi.fn().mockRejectedValue(new ApiError("Initial /models test and discovery failed. The connection was saved; check the URL and credential, then retry sync.", 502));
    const client = api({ createProvider });
    render(<ProviderListPage portalApi={client} />);
    await userEvent.click((await screen.findAllByRole("button", { name: /Add connection/i }))[0]);
    await userEvent.type(screen.getByLabelText(/Provider brand/i), "Acme AI");
    await userEvent.type(screen.getByLabelText(/Private connection label/i), "EU primary");
    await userEvent.type(screen.getByLabelText(/OpenAI compatible HTTPS URL/i), "https://eu.example.test/v1");
    await userEvent.type(screen.getByLabelText(/Provider credential/i), "secret-once");
    await userEvent.click(screen.getByRole("button", { name: /Test & fetch models/i }));
    expect(await screen.findByRole("alert")).toHaveTextContent(/Initial \/models test and discovery failed/i);
    expect(createProvider).toHaveBeenCalledTimes(1);
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
  });

  it("keeps_unpriced_offer_off_user_catalog", async () => {
    render(<ProviderListPage portalApi={api({ listOperatorOffers: vi.fn().mockResolvedValue([{ ...offer, activePrice: null, pendingPrice: null, available: true }]) })} />);
    await openOffer();
    expect(screen.getAllByText(/Price required/i).length).toBeGreaterThan(0);
    expect(screen.getByRole("switch", { name: /Available to developers/i })).toBeDisabled();
  });

  it("shows_pending_price_beside_active_price", async () => {
    render(<ProviderListPage portalApi={api()} />);
    await openOffer();
    expect(screen.getByText(/Active price/i)).toBeInTheDocument();
    expect(screen.getByText(/Pending price/i)).toBeInTheDocument();
    expect(screen.getByText(/\$1\.25/)).toBeInTheDocument();
  });

  it("blocks_mismatched_fallback_with_reason", async () => {
    render(<ProviderListPage portalApi={api()} />);
    await openOffer();
    expect(screen.getAllByText(/Rate mismatch/i).length).toBeGreaterThan(0);
    expect(screen.getByText(/cannot serve requests until its price matches the approved offer/i)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Move US fallback up/i })).toBeDisabled();
  });

  it("offer_toggle_is_distinct_from_connection_toggle", async () => {
    const client = api();
    render(<ProviderListPage portalApi={client} />);
    await openOffer();
    const offerSwitch = screen.getByRole("switch", { name: /Available to developers/i });
    await userEvent.click(offerSwitch);
    expect(client.setOfferAvailable).toHaveBeenCalledWith("offer-1", false);
    expect(client.setRouteAvailability).not.toHaveBeenCalled();
    await userEvent.click(screen.getByRole("switch", { name: /Enable route EU primary/i }));
    await waitFor(() => expect(client.setRouteAvailability).toHaveBeenCalledWith("route-1", false));
  });

  it("route_order_is_keyboard_controllable", async () => {
    const routableOffer = { ...offer, routes: offer.routes.map((route) => ({ ...route, reviewRequired: false, priceStatus: "matching" })) };
    const client = api({ listOperatorOffers: vi.fn().mockResolvedValue([routableOffer]) });
    render(<ProviderListPage portalApi={client} />);
    await openOffer();
    const move = screen.getByRole("button", { name: /Move US fallback up/i });
    move.focus();
    await userEvent.keyboard("{Enter}");
    expect(client.updateRouteOrder).toHaveBeenCalledWith("offer-1", ["conn-2", "conn-1"]);
  });

  it("allows fresh matching routes to be explicitly reconfirmed", async () => {
    const reconfirmableOffer = { ...offer, routes: [
      offer.routes[0], { ...offer.routes[1], reviewRequired: true, priceStatus: "matching" },
    ] };

    const client = api({ listOperatorOffers: vi.fn().mockResolvedValue([reconfirmableOffer]) });

    render(<ProviderListPage portalApi={client} />);
    await openOffer();
    expect(screen.getAllByText(/Reconfirmation required/i).length).toBeGreaterThan(0);
    const routeSwitch = screen.getByRole("switch", { name: /Enable route US fallback/i });
    expect(routeSwitch).toBeEnabled();
    await userEvent.click(routeSwitch);
    await waitFor(() => expect(client.setRouteAvailability).toHaveBeenCalledWith("route-2", true));
  });

  it("shows a visible error when publishing an offer fails", async () => {
    const client = api({ setOfferAvailable: vi.fn().mockRejectedValue(new Error("blocked")) });
    render(<ProviderListPage portalApi={client} />);
    await openOffer();
    await userEvent.click(screen.getByRole("switch", { name: /Available to developers/i }));
    expect(await screen.findByRole("alert")).toHaveTextContent(/could not update model availability/i);
  });

  it("includes an optional cached-input rate in a saved price suggestion", async () => {
    const updateOfferPrice = vi.fn().mockResolvedValue({ id: "suggestion-1", offerId: "offer-1", status: "pending" });
    const client = api({ updateOfferPrice });
    render(<ProviderListPage portalApi={client} />);
    await openOffer();
    await userEvent.clear(screen.getByLabelText(/Cached input USD per 1M tokens/i));
    await userEvent.type(screen.getByLabelText(/Cached input USD per 1M tokens/i), "0.15");
    await userEvent.click(screen.getByRole("button", { name: /Save suggestion/i }));
    await waitFor(() => expect(updateOfferPrice).toHaveBeenCalledWith("offer-1", expect.objectContaining({ cachedInputUsdPerMillion: "0.15" })));
  });

  it("maps an unconfirmed upstream model only to a canonical offer from the same brand", async () => {
    const canonicalOffer = { ...offer, id: "offer-2", canonicalModelId: "acme/model-canonical", displayName: "Canonical Model", routes: [] };
    const otherBrandOffer = { ...canonicalOffer, id: "offer-3", brandSlug: "other", brandName: "Other AI", canonicalModelId: "other/model" };

    const unconfirmedOffer = { ...offer, routes: [
      offer.routes[0], { ...offer.routes[1], reviewRequired: false, priceStatus: "unconfirmed" },
    ] };

    const mapConnectionModel = vi.fn().mockResolvedValue(undefined);
    const client = api({ listOperatorOffers: vi.fn().mockResolvedValue([unconfirmedOffer, canonicalOffer, otherBrandOffer]), mapConnectionModel });
    render(<ProviderListPage portalApi={client} />);
    await openOffer();
    expect(screen.getByRole("option", { name: /Canonical Model/ })).toBeInTheDocument();
    expect(screen.queryByRole("option", { name: /Other AI/ })).not.toBeInTheDocument();
    await userEvent.selectOptions(screen.getByLabelText(/Canonical model for US fallback/i), "offer-2");
    await userEvent.click(screen.getByRole("button", { name: /Map US fallback/i }));
    await waitFor(() => expect(mapConnectionModel).toHaveBeenCalledWith("conn-2", "model-x", "offer-2"));
  });

  it("operator_can_edit_user_allowance_period", async () => {
    const save = vi.fn().mockResolvedValue(undefined);
    render(<AllowanceEditor person={person} onSave={save} />);
    await userEvent.clear(screen.getByLabelText(/USD allowance/i));
    await userEvent.type(screen.getByLabelText(/USD allowance/i), "18.75");
    await userEvent.selectOptions(screen.getByLabelText(/Allowance period/i), "daily");
    await userEvent.click(screen.getByRole("button", { name: /Save allowance/i }));
    await waitFor(() => expect(save).toHaveBeenCalledWith({ allowanceUsd: "18.75", allowancePeriod: "daily", rpmLimit: 30 }));
  });

  it("operator_can_edit_connection_cap_without_float_conversion", async () => {
    const save = vi.fn().mockResolvedValue(undefined);
    const client = api({ updateConnectionBudget: save });
    render(<ConnectionBudgetEditor connection={connection} portalApi={client} onSaved={vi.fn()} />);
    await userEvent.click(screen.getByRole("button", { name: /Edit cap for EU primary/i }));
    await userEvent.clear(screen.getByLabelText(/Connection cap USD/i));
    await userEvent.type(screen.getByLabelText(/Connection cap USD/i), "45.125000001");
    await userEvent.selectOptions(screen.getByLabelText(/Cap period/i), "monthly");
    await userEvent.clear(screen.getByLabelText(/Safety reserve USD/i));
    await userEvent.type(screen.getByLabelText(/Safety reserve USD/i), "4.25");
    await userEvent.click(screen.getByRole("button", { name: /Save connection budget/i }));
    await waitFor(() => expect(save).toHaveBeenCalledWith("conn-1", { limitUsd: "45.125000001", period: "monthly", reserveUsd: "4.25" }));
  });

  it("allowance_editor_displays_berlin_reset", () => {
    render(<AllowanceEditor person={person} onSave={vi.fn()} />);
    expect(screen.getByText(/Resets in Europe\/Berlin/i)).toBeInTheDocument();
    expect(screen.getByText(/Monday, 28 September 2026/i)).toBeInTheDocument();
  });

  it("operator_usage_filters_by_connection", async () => {
    const listOperatorActivity = vi.fn().mockResolvedValue({ items: [], nextCursor: null });
    render(<OperatorUsagePage portalApi={api({ listProviders: vi.fn().mockResolvedValue([connection]), listOperatorActivity })} />);
    await screen.findByLabelText(/Connection/i);
    await userEvent.selectOptions(screen.getByLabelText(/Connection/i), "conn-1");
    await waitFor(() => expect(listOperatorActivity).toHaveBeenLastCalledWith(expect.objectContaining({ connectionId: "conn-1" })));
  });

  it("format_usd_keeps_small_nonzero_charges_visible", () => {
    expect(formatUsd("0.000000001")).not.toBe("$0.00");
    expect(formatUsd("0.000000001")).toContain("0.000000001");
    expect(formatUsd("0.0000000001")).toBe("<$0.000000001");
    expect(formatUsd("0")).toBe("$0.00");
    expect(ratioPercent("1", "3")).toBe(33);
    expect(ratioPercent("4", "3")).toBe(100);
    expect(ratioPercent("0.5", "10")).toBe(5);
    expect(ratioPercent("1", "0")).toBeNull();
  });

  it("groups_connections_by_brand_and_keeps_private_labels", async () => {
    render(<ProviderListPage portalApi={api()} />);
    await openBrand();
    expect(screen.getByText("EU primary")).toBeInTheDocument();
  });
});
