import { useState } from "react";
import * as Tabs from "@radix-ui/react-tabs";
import { CartesianGrid, Line, LineChart, Tooltip, XAxis, YAxis } from "recharts";
import type { AnalyticsUsagePoint } from "../../contracts/api";
import { count } from "../../lib/format";
import { formatUsd, formatUsdExact } from "../../lib/money";
import { ChartContainer } from "./ChartContainer";

type Metric = "requests" | "tokens" | "spend";

function isMetric(value: string): value is Metric {
  return value === "requests" || value === "tokens" || value === "spend";
}

function dateLabel(day: string): string {
  const date = new Date(`${day}T12:00:00Z`);

  return new Intl.DateTimeFormat("en-GB", { day: "numeric", month: "short", timeZone: "Europe/Berlin" }).format(date);
}

function spendCoverageLabel(point: AnalyticsUsagePoint): string {
  return point.unpricedRequests > 0
    ? `Known spend only · ${count(point.unpricedRequests)} unpriced requests`
    : "Fully priced · 0 unpriced requests";
}

export function formatSpendAxisTick(value: number): string {
  if (!Number.isFinite(value)) return "Not reported";

  if (value > 0 && value < 0.000001) return `≈$${value.toExponential(1)}`;

  return formatUsd(value.toFixed(9));
}

export function formatSpendTooltipValue(point: AnalyticsUsagePoint): string {
  const coverage = spendCoverageLabel(point);

  if (point.estimatedSpendUsd == null) return `Not reported · ${coverage}`;

  if (point.unpricedRequests > 0) return `${formatUsdExact(point.estimatedSpendUsd)} · ${coverage}`;

  return formatUsdExact(point.estimatedSpendUsd);
}

export function formatSpendTooltipForDay(day: string, series: AnalyticsUsagePoint[]): string {
  const point = series.find((entry) => entry.day === day);

  return point ? formatSpendTooltipValue(point) : "Not reported";
}

export function UsageTrendChart({ series }: { series: AnalyticsUsagePoint[] }) {
  const [metric, setMetric] = useState<Metric>("requests");
  const key = metric === "requests" ? "requests" : metric === "tokens" ? "totalTokens" : "estimatedSpendUsd";
  const label = metric === "requests" ? "Requests" : metric === "tokens" ? "Tokens" : "Spend";
  const points = series.map((point) => ({ ...point, chartValue: point[key] == null ? null : Number(point[key]) }));
  const unpricedSpendDays = metric === "spend" ? series.filter((point) => point.unpricedRequests > 0) : [];

  function valueText(value: number | string | null) {
    if (value == null || !Number.isFinite(Number(value))) return "Not reported";

    return metric === "spend" ? formatUsdExact(String(value)) : count(Number(value));
  }

  return <section className="section-block analytics-chart-card" aria-labelledby="usage-trend-heading">
    <div className="section-heading"><div><h2 id="usage-trend-heading">Usage trend</h2><p>{metric === "spend" ? "Daily known spend · hover each day for its cost coverage." : `Daily ${label.toLowerCase()} for the selected period.`}</p></div><Tabs.Root value={metric} onValueChange={(value) => { if (isMetric(value)) setMetric(value); }} className="metric-tabs"><Tabs.List aria-label="Usage trend metric"><Tabs.Trigger value="requests">Requests</Tabs.Trigger><Tabs.Trigger value="tokens">Tokens</Tabs.Trigger><Tabs.Trigger value="spend">Spend</Tabs.Trigger></Tabs.List></Tabs.Root></div>
    {unpricedSpendDays.length > 0 && <section className="daily-spend-coverage" aria-label="Unpriced daily spend">
      <div className="daily-spend-coverage-heading"><strong>Known spend only</strong><span>{count(unpricedSpendDays.length)} days include unpriced requests</span></div>
      <ul>{unpricedSpendDays.map((point) => <li key={point.day}><time dateTime={point.day}>{dateLabel(point.day)}</time><span>{spendCoverageLabel(point)}</span>{point.estimatedSpendUsd == null && <small>No priced spend reported</small>}</li>)}</ul>
    </section>}
    {points.length ? <>
      <ChartContainer ariaLabel={`Daily ${label.toLowerCase()} chart`} height={230}><LineChart data={points} accessibilityLayer margin={{ top: 10, right: 12, left: 0, bottom: 0 }}>
        <CartesianGrid stroke="var(--chart-grid)" vertical={false} />
        <XAxis dataKey="day" tickFormatter={dateLabel} tick={{ fill: "var(--muted)", fontSize: 10 }} tickLine={false} axisLine={false} minTickGap={26} />
        <YAxis width={46} tickFormatter={(value: number) => metric === "spend" ? formatSpendAxisTick(value) : count(value)} tick={{ fill: "var(--muted)", fontSize: 10 }} tickLine={false} axisLine={false} />
        <Tooltip labelFormatter={(day) => {
          const point = series.find((entry) => entry.day === String(day));
          const formattedDay = dateLabel(String(day));

          return metric === "spend" && point ? `${formattedDay} · ${spendCoverageLabel(point)}` : formattedDay;
        }} formatter={(value, _name, item) => {
          if (metric === "spend") {
            const hoveredDay = String(item.payload?.day ?? "");

            return [formatSpendTooltipForDay(hoveredDay, series), label];
          }

          return [value == null ? "Not reported" : count(Number(value)), label];
        }} contentStyle={{ background: "var(--elevated)", border: "1px solid var(--border-strong)", borderRadius: 6, color: "var(--text)" }} />
        <Line type="monotone" dataKey="chartValue" name={label} stroke="var(--chart-primary)" strokeWidth={2} dot={{ r: 2, fill: "var(--chart-primary)" }} activeDot={{ r: 4 }} connectNulls={false} isAnimationActive={false} />
      </LineChart></ChartContainer>
      <table className="sr-only" aria-label="Usage trend data"><caption>Daily {label.toLowerCase()} values</caption><thead><tr><th scope="col">Date</th><th scope="col">{label}</th>{metric === "spend" && <th scope="col">Cost coverage</th>}</tr></thead><tbody>{points.map((point) => <tr key={point.day}><td>{point.day}</td><td>{valueText(point[key])}</td>{metric === "spend" && <td>{spendCoverageLabel(point)}</td>}</tr>)}</tbody></table>
    </> : <div className="chart-placeholder"><span>No usage data yet</span><small>The trend will fill from recorded request events.</small></div>}
  </section>;
}
