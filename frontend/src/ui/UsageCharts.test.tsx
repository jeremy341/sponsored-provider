import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";
import type { ModelSpendRecord } from "../contracts/api";
import { buildSpendSlices } from "./charts/spendChartData";
import { ModelSpendChart, spendSliceColor, spendTooltipValue } from "./charts/ModelSpendChart";
import { UsageTrendChart } from "./charts/UsageTrendChart";

const models: ModelSpendRecord[] = [
  { id: "offer:nimbus:model-a", modelId: "nimbus::model-a", providerName: "Nimbus", requests: 4, totalTokens: 400, spendUsd: "0.90" },
  { id: "offer:nimbus:model-b", modelId: "nimbus::model-b", providerName: "Nimbus", requests: 3, totalTokens: 300, spendUsd: "0.05" },
  { id: "offer:nimbus:model-c", modelId: "nimbus::model-c", providerName: "Nimbus", requests: 2, totalTokens: 200, spendUsd: "0.03" },
  { id: "offer:nimbus:model-d", modelId: "nimbus::model-d", providerName: "Nimbus", requests: 1, totalTokens: 100, spendUsd: "0.02" },
];

describe("usage chart components", () => {
  it("assigns a distinct stable color to every visible model slice", () => {
    const colors = Array.from({ length: 12 }, (_, index) => spendSliceColor(index));

    expect(new Set(colors).size).toBe(colors.length);
    expect(colors).toEqual(Array.from({ length: 12 }, (_, index) => spendSliceColor(index)));
  });

  it("groups model shares below three percent and retains exact total spend", () => {
    const result = buildSpendSlices(models, "1.00");
    expect(result.state).toBe("ready");

    if (result.state !== "ready") return;
    expect(result.totalSpendUsd).toBe("1");
    expect(result.slices.find((slice) => slice.name === "Other models")?.spendUsd).toBe("0.02");
    expect(result.slices.some((slice) => slice.name === "Nimbus / nimbus::model-c")).toBe(true);
  });

  it("preserves a single sub-nano-USD value without rounding", () => {
    const result = buildSpendSlices([{ id: "route-tiny", modelId: "tiny", providerName: "Nimbus", requests: 1, totalTokens: 1, spendUsd: "0.0000000005" }], "0.0000000005");

    expect(result).toMatchObject({ state: "ready", totalSpendUsd: "0.0000000005", slices: [{ id: "route-tiny", spendUsd: "0.0000000005", value: 1, percent: 100 }] });
  });

  it("reconciles arbitrary sub-nano model spends without rounding their total", () => {
    const result = buildSpendSlices([
      { id: "nano-route-1", modelId: "model-a", providerName: "Nimbus", requests: 1, totalTokens: 1, spendUsd: "0.0000000004" },
      { id: "nano-route-2", modelId: "model-b", providerName: "Nimbus", requests: 1, totalTokens: 1, spendUsd: "0.0000000004" },
    ], "0.0000000008");

    expect(result).toMatchObject({
      state: "ready",
      totalSpendUsd: "0.0000000008",
      slices: [
        { id: "nano-route-1", spendUsd: "0.0000000004", value: 0.5, percent: 50 },
        { id: "nano-route-2", spendUsd: "0.0000000004", value: 0.5, percent: 50 },
      ],
    });

    render(<ModelSpendChart models={[
      { id: "nano-route-1", modelId: "model-a", providerName: "Nimbus", requests: 1, totalTokens: 1, spendUsd: "0.0000000004" },
      { id: "nano-route-2", modelId: "model-b", providerName: "Nimbus", requests: 1, totalTokens: 1, spendUsd: "0.0000000004" },
    ]} knownSpendUsd="0.0000000008" unpricedRequests={0} />);
    expect(screen.getByText("$0.0000000008")).toBeInTheDocument();
    expect(screen.getAllByText("$0.0000000004")).toHaveLength(2);
  });

  it("keeps identical canonical IDs distinct when provider brands differ", () => {
    const providerOffers = [
      { id: "offer:nimbus:deepseek-v4-flash", modelId: "deepseek/v4-flash", providerName: "Nimbus", requests: 1, totalTokens: 10, spendUsd: "0.60" },
      { id: "offer:openrouter:deepseek-v4-flash", modelId: "deepseek/v4-flash", providerName: "OpenRouter", requests: 2, totalTokens: 20, spendUsd: "0.40" },
    ];

    const result = buildSpendSlices(providerOffers, "1.00");

    expect(result.state).toBe("ready");

    if (result.state !== "ready") return;

    expect(result.slices).toMatchObject([
      { id: "offer:nimbus:deepseek-v4-flash", name: "Nimbus / deepseek/v4-flash" },
      { id: "offer:openrouter:deepseek-v4-flash", name: "OpenRouter / deepseek/v4-flash" },
    ]);
  });

  it("uses opaque row IDs when two provider offers have the same visible label", () => {
    const duplicateLabels: ModelSpendRecord[] = [
      { id: "provider-brand-one-row", modelId: "deepseek/v4-flash", providerName: "Nimbus", requests: 1, totalTokens: 10, spendUsd: "0.60" },
      { id: "provider-brand-two-row", modelId: "deepseek/v4-flash", providerName: "Nimbus", requests: 2, totalTokens: 20, spendUsd: "0.40" },
    ];

    const result = buildSpendSlices(duplicateLabels, "1.00");

    expect(result.state).toBe("ready");

    if (result.state !== "ready") return;

    const slicesById = new Map(result.slices.map((slice) => [slice.id, slice]));
    expect(result.slices.map((slice) => slice.name)).toEqual(["Nimbus / deepseek/v4-flash", "Nimbus / deepseek/v4-flash"]);
    expect(result.slices.map((slice) => slice.id)).toEqual(["provider-brand-one-row", "provider-brand-two-row"]);
    expect(spendTooltipValue("provider-brand-two-row", slicesById)).toBe("$0.40 · 40%");

    render(<ModelSpendChart models={duplicateLabels} knownSpendUsd="1.00" unpricedRequests={0} />);
    expect(screen.getAllByText("Nimbus / deepseek/v4-flash")).toHaveLength(4);
    expect(screen.getAllByRole("listitem")).toHaveLength(2);
  });

  it("renders a complete spend donut with percentage legend and a semantic table", () => {
    render(<ModelSpendChart models={models} knownSpendUsd="1.00" unpricedRequests={0} />);
    expect(screen.getByRole("group", { name: /model spend distribution/i })).toBeInTheDocument();
    expect(screen.getByText("100% of known spend")).toBeInTheDocument();
    expect(screen.getByRole("table", { name: /model spend distribution data/i })).toBeInTheDocument();
    expect(screen.getAllByText("Other models")).toHaveLength(2);
  });

  it("labels partial-cost coverage instead of describing unknown spend as free", () => {
    render(<ModelSpendChart models={[...models, { id: "offer:x:model-x", modelId: "x", providerName: "X", requests: 2, totalTokens: null, spendUsd: null }]} knownSpendUsd="1.00" unpricedRequests={2} />);
    expect(screen.getByText(/known spend only/i)).toBeInTheDocument();
    expect(screen.getByText(/2 requests.*cost not reported/i)).toBeInTheDocument();
  });

  it("marks the spend chart incomplete when its model rows do not reconcile", () => {
    const { container } = render(<ModelSpendChart models={models} knownSpendUsd="1.50" unpricedRequests={0} />);
    expect(screen.getByText(/breakdown does not reconcile/i)).toBeInTheDocument();
    expect(container.querySelector("svg.recharts-surface")).not.toBeInTheDocument();
  });

  it("exposes the selected trend metric as a chart and readable data table", async () => {
    render(<UsageTrendChart series={[{ day: "2026-09-01", requests: 2, totalTokens: 10, estimatedSpendUsd: "0.25", unpricedRequests: 0 }]} />);
    expect(screen.getByRole("group", { name: /daily requests/i })).toBeInTheDocument();
    await userEvent.click(screen.getByRole("tab", { name: "Spend" }));
    expect(within(screen.getByRole("table", { name: /usage trend data/i })).getByText("$0.25")).toBeInTheDocument();
  });

  it("shows day-specific incomplete spend coverage in the spend view", async () => {
    render(<UsageTrendChart series={[{ day: "2026-09-02", requests: 4, totalTokens: 12, estimatedSpendUsd: "0.40", unpricedRequests: 2 }]} />);
    await userEvent.click(screen.getByRole("tab", { name: "Spend" }));

    const table = screen.getByRole("table", { name: /usage trend data/i });
    expect(within(table).getByText("Known spend only · 2 unpriced requests")).toBeInTheDocument();
  });

  it("visibly lists unpriced-only days without plotting them as zero spend", async () => {
    render(<UsageTrendChart series={[{ day: "2026-09-03", requests: 2, totalTokens: null, estimatedSpendUsd: null, unpricedRequests: 2 }]} />);
    await userEvent.click(screen.getByRole("tab", { name: "Spend" }));

    const coverage = screen.getByRole("region", { name: /unpriced daily spend/i });
    expect(within(coverage).getByText("3 Sept")).toBeInTheDocument();
    expect(within(coverage).getByText("Known spend only · 2 unpriced requests")).toBeInTheDocument();
    expect(within(coverage).getByText("No priced spend reported")).toBeInTheDocument();
    expect(within(screen.getByRole("table", { name: /usage trend data/i })).getByText("Not reported")).toBeInTheDocument();
  });
});
