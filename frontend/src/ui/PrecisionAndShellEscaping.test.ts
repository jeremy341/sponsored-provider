import { describe, expect, it } from "vitest";
import type { AnalyticsUsagePoint } from "../contracts/api";
import { createModelExamples, quotePosixShellArgument } from "./developer/ModelCodeExamples";
import { formatSpendAxisTick, formatSpendTooltipForDay, formatSpendTooltipValue } from "./charts/UsageTrendChart";

describe("exact spend tooltip formatting", () => {
  it("formats tiny numeric spend ticks approximately instead of treating exponent notation as invalid USD", () => {
    expect(formatSpendAxisTick(Number("0.0000000008"))).toBe("≈$8.0e-10");
  });

  it("preserves every sub-nano digit from the hovered day's source value", () => {
    const point: AnalyticsUsagePoint = {
      day: "2026-09-02",
      requests: 2,
      totalTokens: 10,
      estimatedSpendUsd: "0.0000000008",
      unpricedRequests: 1,
    };

    expect(formatSpendTooltipValue(point)).toBe("$0.0000000008 · Known spend only · 1 unpriced requests");
    expect(formatSpendTooltipForDay("2026-09-02", [point])).toBe("$0.0000000008 · Known spend only · 1 unpriced requests");
  });

  it("reports unknown spend and daily coverage instead of showing zero", () => {
    const point: AnalyticsUsagePoint = {
      day: "2026-09-03",
      requests: 2,
      totalTokens: null,
      estimatedSpendUsd: null,
      unpricedRequests: 2,
    };

    expect(formatSpendTooltipValue(point)).toBe("Not reported · Known spend only · 2 unpriced requests");
  });
});

describe("cURL shell argument quoting", () => {
  it("quotes apostrophes without breaking the single-quoted JSON argument", () => {
    const payload = JSON.stringify({ model: "vendor/model's", messages: [{ role: "user", content: "Hello" }] });
    const shellArgument = `'{"model":"vendor/model'"'"'s","messages":[{"role":"user","content":"Hello"}]}'`;

    expect(quotePosixShellArgument(payload)).toBe(shellArgument);
    expect(createModelExamples("vendor/model's", "https://provider.example/v1").curl).toContain(`-d ${shellArgument}`);
  });
});
