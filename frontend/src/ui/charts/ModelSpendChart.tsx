import { Cell, Pie, PieChart, Tooltip } from "recharts";
import type { ModelSpendRecord } from "../../contracts/api";
import { count } from "../../lib/format";
import { formatUsdExact } from "../../lib/money";
import { ChartContainer } from "./ChartContainer";
import { buildSpendSlices, type SpendSlice } from "./spendChartData";

const SPEND_SERIES = ["#e6b450", "#59c2ff", "#aad94c", "#d2a6ff", "#f07178"];

export function spendSliceColor(index: number): string {
  return SPEND_SERIES[index % SPEND_SERIES.length];
}

export function spendTooltipValue(rowId: string, slicesById: ReadonlyMap<string, SpendSlice>): string {
  const slice = slicesById.get(rowId);

  return slice ? `${formatUsdExact(slice.spendUsd)} · ${slice.percent}%` : "Not reported";
}

export function ModelSpendChart({ models, knownSpendUsd, unpricedRequests }: { models: ModelSpendRecord[]; knownSpendUsd: string | null; unpricedRequests: number }) {
  const breakdown = buildSpendSlices(models, knownSpendUsd);
  const hasUnknown = unpricedRequests > 0 || models.some((model) => model.spendUsd == null && model.requests > 0);
  const tooltipData = new Map(breakdown.state === "ready" ? breakdown.slices.map((slice) => [slice.id, slice]) : []);

  return <section className="section-block analytics-chart-card" aria-labelledby="model-spend-heading">
    <div className="section-heading"><div><h2 id="model-spend-heading">Where spend went</h2><p>{hasUnknown ? "Known spend only · incomplete cost coverage" : "Distribution of priced spend"}</p></div><span className="spend-chart-total">{breakdown.state === "ready" || breakdown.state === "empty" ? formatUsdExact(breakdown.totalSpendUsd) : "Not reconciled"}</span></div>
    {hasUnknown && <p className="chart-coverage" role="status">{unpricedRequests > 0 ? `${count(unpricedRequests)} requests have cost not reported.` : "Some request costs were not reported."} Unknown costs are excluded, not treated as free.</p>}
    {breakdown.state === "incomplete" ? <div className="chart-placeholder" role="status"><span>Spend breakdown unavailable</span><small>{breakdown.reason}</small></div> : breakdown.state === "empty" ? <div className="chart-placeholder"><span>No priced spend in this period</span><small>There is no positive known spend to distribute yet.</small></div> : <>
      <p className="chart-share-note">100% of known spend</p>
      <div className="model-spend-layout">
        <ChartContainer ariaLabel="Model spend distribution" height={232}><PieChart accessibilityLayer>
          <Pie data={breakdown.slices} dataKey="value" nameKey="name" innerRadius="58%" outerRadius="84%" paddingAngle={1} stroke="var(--surface)" strokeWidth={2} isAnimationActive={false}>
            {breakdown.slices.map((slice, index) => <Cell key={slice.id} fill={spendSliceColor(index)} />)}
          </Pie>
          <Tooltip formatter={(_value, _name, item) => {
            const rowId = String(item.payload?.id ?? "");

            return [spendTooltipValue(rowId, tooltipData), "Spend"];
          }} contentStyle={{ background: "var(--elevated)", border: "1px solid var(--border-strong)", borderRadius: 6, color: "var(--text)" }} />
        </PieChart></ChartContainer>
        <ul className="model-spend-legend" aria-label="Model spend percentages">{breakdown.slices.map((slice, index) => <li key={slice.id}><span className="chart-legend-dot" style={{ background: spendSliceColor(index) }} aria-hidden="true" /><span className="model-spend-name" title={slice.name}>{slice.name}</span><span className="model-spend-percent">{slice.percent}%</span></li>)}</ul>
      </div>
      <table className="sr-only" aria-label="Model spend distribution data"><caption>Priced model spend totals and percentages</caption><thead><tr><th scope="col">Model</th><th scope="col">Spend</th><th scope="col">Share</th><th scope="col">Requests</th></tr></thead><tbody>{breakdown.slices.map((slice) => <tr key={slice.id}><td>{slice.name}</td><td>{formatUsdExact(slice.spendUsd)}</td><td>{slice.percent}%</td><td>{count(slice.requests)}</td></tr>)}</tbody></table>
    </>}
  </section>;
}
