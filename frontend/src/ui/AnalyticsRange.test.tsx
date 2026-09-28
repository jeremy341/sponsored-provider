import { render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import type { DashboardAnalytics } from "../contracts/api";
import type { OperatorDashboard } from "../contracts/api";
import { api } from "../lib/api";
import { App } from "./App";
import { DashboardAnalyticsPanel } from "./DashboardAnalyticsPanel";
import { pickSelect } from "../test/select";

const analytics: DashboardAnalytics = {
  period: { key: "current_month", from: "2026-09-01T00:00:00+02:00", to: "2026-09-28T10:00:00+02:00", timezone: "Europe/Berlin" },
  summary: null,
  series: [],
  topModels: [{ modelId: "nimbus::period-model", providerName: "Nimbus", requests: 7, totalTokens: 140, estimatedSpendUsd: "0.12" }],
  modelSpend: [],
  knownSpendUsd: "0",
  unpricedRequests: 0,
};

const operatorDashboard: OperatorDashboard = {
  usage: null,
  series: [],
  topModels: [],
  providers: [],
  recentActivity: [],
  guardrails: null,
  analytics,
};

afterEach(() => {
  vi.restoreAllMocks();
  window.history.replaceState({}, "", "/");
});

describe("dashboard analytics range", () => {
  it("renders the operator overview with the backend analytics period contract", async () => {
    window.history.replaceState({}, "", "/operator");
    vi.spyOn(api, "getSession").mockResolvedValue({ user: { displayName: "Operator", email: null }, role: "operator", csrfToken: "csrf" });
    vi.spyOn(api, "getOperatorDashboard").mockResolvedValue(operatorDashboard);

    render(<App />);

    expect(await screen.findByText(/September 2026/i)).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Usage analytics" })).toBeInTheDocument();
  });

  it("defaults to this month and changes the shared selected range", async () => {
    const onRangeChange = vi.fn();
    render(<DashboardAnalyticsPanel analytics={analytics} range="current_month" onRangeChange={onRangeChange} />);
    expect(screen.getByRole("combobox", { name: /analytics period/i })).toHaveTextContent("This month");
    expect(screen.getByText(/September 2026/i)).toBeInTheDocument();
    await pickSelect(/analytics period/i, "Last 30 days");
    expect(onRangeChange).toHaveBeenCalledWith("30d");
  });

  it("keeps allowance reset controls outside the analytics range module", () => {
    render(<DashboardAnalyticsPanel analytics={analytics} range="current_month" onRangeChange={vi.fn()} />);
    expect(screen.getByText(/your allowance reset stays on its assigned cycle/i)).toBeInTheDocument();
  });

  it("renders the selected-window model ranking rather than reusing lifetime top models", () => {
    render(<DashboardAnalyticsPanel analytics={analytics} range="current_month" onRangeChange={vi.fn()} />);
    expect(screen.getByRole("heading", { name: "Top models this period" })).toBeInTheDocument();
    expect(screen.getByText("Nimbus / nimbus::period-model")).toBeInTheDocument();
    expect(screen.getByText("7")).toBeInTheDocument();
  });

  it("qualifies period ranking rows with provider brand for colliding canonical IDs", () => {
    const data = { ...analytics, topModels: [
      { modelId: "deepseek/v4-flash", providerName: "Nimbus", requests: 1, totalTokens: 10, estimatedSpendUsd: "0.10" },
      { modelId: "deepseek/v4-flash", providerName: "OpenRouter", requests: 2, totalTokens: 20, estimatedSpendUsd: "0.20" },
    ] };

    render(<DashboardAnalyticsPanel analytics={data} range="current_month" onRangeChange={vi.fn()} />);
    expect(screen.getByText("Nimbus / deepseek/v4-flash")).toBeInTheDocument();
    expect(screen.getByText("OpenRouter / deepseek/v4-flash")).toBeInTheDocument();
  });
});
