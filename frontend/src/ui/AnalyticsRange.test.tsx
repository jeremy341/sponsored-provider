import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import type { DashboardAnalytics } from "../contracts/api";
import { DashboardAnalyticsPanel } from "./DashboardAnalyticsPanel";

const analytics: DashboardAnalytics = {
  window: { range: "current_month", from: "2026-09-01T00:00:00+02:00", to: "2026-09-28T10:00:00+02:00", timezone: "Europe/Berlin" },
  summary: null,
  series: [],
  topModels: [{ modelId: "nimbus::period-model", providerName: "Nimbus", requests: 7, totalTokens: 140, estimatedSpendUsd: "0.12" }],
  modelSpend: [],
  knownSpendUsd: "0",
  unpricedRequests: 0,
};

describe("dashboard analytics range", () => {
  it("defaults to this month and changes the shared selected range", async () => {
    const onRangeChange = vi.fn();
    render(<DashboardAnalyticsPanel analytics={analytics} range="current_month" onRangeChange={onRangeChange} />);
    expect(screen.getByRole("combobox", { name: /analytics period/i })).toHaveValue("current_month");
    expect(screen.getByText(/September 2026/i)).toBeInTheDocument();
    await userEvent.selectOptions(screen.getByRole("combobox", { name: /analytics period/i }), "30d");
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
