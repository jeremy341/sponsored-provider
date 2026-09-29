import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, useLocation } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";
import type { ActivityEvent, ApiKeyRecord, DeveloperProviderStatus, ModelRecord } from "../../contracts/api";
import { api, apiExtensions, streamPlayground } from "../../lib/api";
import { PlaygroundPage } from "./PlaygroundPage";
import { LogsPage } from "./LogsPage";
import { DeveloperProvidersPage } from "./DeveloperProvidersPage";

vi.mock("../../lib/api", async (importOriginal) => {
  const actual = await importOriginal<typeof import("../../lib/api")>();
  return { ...actual, streamPlayground: vi.fn() };
});

function RouteProbe() {
  const location = useLocation();
  return <span data-testid="probe">{location.search}</span>;
}

const key: ApiKeyRecord = {
  id: "key-1",
  label: "OpenCode laptop",
  prefix: "sk-sp_abc123",
  modelAccess: { mode: "all_approved" },
  spendCapUsd: null,
  spendUsedUsd: "0",
  spendPeriod: null,
  spendResetAt: null,
  rpmLimit: 60,
  createdAt: "2026-09-01T10:00:00Z",
  lastUsedAt: null,
  status: "active",
};

const model: ModelRecord = {
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
  activeRouteCount: 2,
};

const event: ActivityEvent = {
  id: "evt-1",
  occurredAt: "2026-09-29T12:00:00Z",
  modelId: "nimbus::deepseek/v4-flash",
  providerName: "Nimbus",
  keyLabel: "OpenCode laptop",
  inputTokens: 120,
  outputTokens: 80,
  totalTokens: 200,
  estimatedCostUsd: "0.000132",
  costSource: "gateway_estimate",
  requestId: "req-xyz",
  status: "success",
  errorCategory: null,
  latencyMs: 812,
  cachedTokens: null,
};

const provider: DeveloperProviderStatus = {
  provider: "Nimbus",
  models: 3,
  health: "healthy",
  sampleSize: 240,
  successRate: 0.995,
  p50LatencyMs: 420,
  p95LatencyMs: 1400,
  lastActivityAt: "2026-09-29T11:00:00Z",
};

describe("playground", () => {
  afterEach(() => vi.restoreAllMocks());

  function mockApi() {
    vi.spyOn(api, "listKeys").mockResolvedValue([key]);
    vi.spyOn(api, "listModels").mockResolvedValue([model]);
    vi.mocked(streamPlayground).mockImplementation(async ({ onTelemetry }: { onTelemetry: (event: { ttftMs?: number }) => void }) => {
      onTelemetry({ ttftMs: 210 });
      return { text: "Routed answer.", error: null, errorCode: null, usage: { input: 12, output: 8, total: 20 } };
    });
  }

  it("sends a real request and renders the response with measured telemetry and a not-stored notice", async () => {
    mockApi();
    render(<MemoryRouter><PlaygroundPage /></MemoryRouter>);

    await screen.findByRole("combobox", { name: "API key" });
    await screen.findByRole("combobox", { name: "Model" });
    const prompt = screen.getByLabelText("Prompt");
    await userEvent.type(prompt, "Hello router");
    await userEvent.click(screen.getByRole("button", { name: "Send" }));

    expect(await screen.findByText("Routed answer.")).toBeInTheDocument();
    const footer = screen.getByRole("contentinfo", { name: "Request telemetry" });
    expect(within(footer).getByText("Nimbus")).toBeInTheDocument();
    expect(within(footer).getByText(/12 \/ 8/)).toBeInTheDocument();
    expect(within(footer).getByText("success", { exact: false })).toBeInTheDocument();
    expect(screen.getByText(/Not stored/)).toBeInTheDocument();
  });

  it("shows the empty thread guidance before any request", async () => {
    mockApi();
    render(<MemoryRouter><PlaygroundPage /></MemoryRouter>);

    expect(await screen.findByText(/Send a prompt to run a live request/)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Send" })).toBeDisabled();
  });
});

describe("logs", () => {
  afterEach(() => vi.restoreAllMocks());

  function mockApi() {
    vi.spyOn(api, "listActivity").mockResolvedValue({ items: [event], nextCursor: null });
  }

  it("renders the dense table and the metadata-only inspector without prompts", async () => {
    mockApi();
    render(<MemoryRouter><LogsPage title="Logs" description="Request log" /></MemoryRouter>);

    expect(await screen.findByText("nimbus::deepseek/v4-flash")).toBeInTheDocument();
    expect(screen.getByText("OpenCode laptop")).toBeInTheDocument();
    await userEvent.click(screen.getByText("nimbus::deepseek/v4-flash"));
    const inspector = screen.getByRole("complementary", { name: "Request inspector" });
    await userEvent.click(within(inspector).getByRole("tab", { name: "Metadata" }));
    expect(within(inspector).getAllByText("Not stored")).toHaveLength(2);
    expect(within(inspector).getByText("req-xyz")).toBeInTheDocument();
  });

  it("filters by outcome through URL search params", async () => {
    mockApi();
    render(<MemoryRouter initialEntries={["/developer/logs?status=rejected"]}><LogsPage title="Logs" description="Request log" /><RouteProbe /></MemoryRouter>);

    await screen.findByText("nimbus::deepseek/v4-flash");
    await userEvent.click(screen.getByRole("combobox", { name: "Filter by outcome" }));
    const option = await screen.findByRole("option", { name: "Success" });
    await userEvent.click(option);
    await waitFor(() => expect(screen.getByTestId("probe")).toHaveTextContent("status=success"));
  });
});

describe("developer providers", () => {
  afterEach(() => vi.restoreAllMocks());

  function mockApi(providers: DeveloperProviderStatus[]) {
    vi.spyOn(apiExtensions, "listDeveloperProviders").mockResolvedValue(providers);
  }

  it("shows measured health and never operator-only data", async () => {
    mockApi([provider]);
    render(<MemoryRouter><DeveloperProvidersPage /></MemoryRouter>);

    expect(await screen.findByText("Nimbus")).toBeInTheDocument();
    expect(screen.getByText("99.5%")).toBeInTheDocument();
    expect(screen.getByText("420 ms")).toBeInTheDocument();
    expect(screen.getByText(/not visible here/i)).toBeInTheDocument();
    expect(screen.queryByText(/safety reserve/i)).not.toBeInTheDocument();
  });

  it("marks low-traffic providers as having no recent traffic instead of inventing health", async () => {
    mockApi([{ ...provider, sampleSize: 2, successRate: 1, p50LatencyMs: 100, p95LatencyMs: 200, health: "unknown" }]);
    render(<MemoryRouter><DeveloperProvidersPage /></MemoryRouter>);

    expect(await screen.findByText(/No recent traffic/)).toBeInTheDocument();
    const card = screen.getByRole("listitem");
    expect(within(card).getByText("unknown")).toBeInTheDocument();
  });
});
