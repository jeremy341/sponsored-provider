import type { DashboardAnalytics, DashboardRange, ModelUsageRecord } from "../contracts/api";
import { count } from "../lib/format";
import { formatUsdExact } from "../lib/money";
import { ModelSpendChart } from "./charts/ModelSpendChart";
import { UsageTrendChart } from "./charts/UsageTrendChart";

const ranges: Array<{ value: DashboardRange; label: string }> = [
  { value: "current_month", label: "This month" },
  { value: "7d", label: "Last 7 days" },
  { value: "30d", label: "Last 30 days" },
  { value: "90d", label: "Last 90 days" },
];

function isDashboardRange(value: string): value is DashboardRange {
  return ranges.some((entry) => entry.value === value);
}

export function DashboardAnalyticsPanel({ analytics, range, onRangeChange, loading = false }: {
  analytics: DashboardAnalytics | null;
  range: DashboardRange;
  onRangeChange: (range: DashboardRange) => void;
  loading?: boolean;
}) {
  const title = analytics ? periodLabel(analytics) : ranges.find((entry) => entry.value === range)?.label ?? "Selected period";

  return <section className="dashboard-analytics" aria-label="Period analytics">
    <div className="analytics-heading"><div><span className="eyebrow">Selected period · Europe/Berlin</span><h2>Usage analytics</h2><p>{title} · This selector changes charts only; your allowance reset stays on its assigned cycle.</p></div><label className="analytics-range"><span>Analytics period</span><select aria-label="Analytics period" value={range} onChange={(event) => { if (isDashboardRange(event.target.value)) onRangeChange(event.target.value); }}>{ranges.map((entry) => <option key={entry.value} value={entry.value}>{entry.label}</option>)}</select></label></div>
    {loading ? <div className="loading-line" role="status"><span className="sr-only">Loading period analytics</span></div> : analytics ? <>
      <div className="analytics-stat-strip" aria-label={`${title} usage summary`}>
        <AnalyticsStat label="Requests" value={count(analytics.summary?.requests ?? null)} />
        <AnalyticsStat label="Input tokens" value={count(analytics.summary?.inputTokens ?? null)} />
        <AnalyticsStat label="Output tokens" value={count(analytics.summary?.outputTokens ?? null)} />
        <AnalyticsStat label={analytics.unpricedRequests ? "Known spend" : "Spend"} value={formatUsdExact(analytics.knownSpendUsd)} />
      </div>
      <div className="analytics-charts-grid"><UsageTrendChart series={analytics.series} /><ModelSpendChart models={analytics.modelSpend} knownSpendUsd={analytics.knownSpendUsd} unpricedRequests={analytics.unpricedRequests} /></div>
      <PeriodModelRanking models={analytics.topModels} />
    </> : <div className="empty-state" role="status"><div><h3>Period analytics unavailable</h3><p>This server has not returned the period analytics contract yet. Lifetime totals remain separate, and no chart will substitute all-time data for the selected range.</p></div></div>}
  </section>;
}

function AnalyticsStat({ label, value }: { label: string; value: string }) {
  return <div><span>{label}</span><strong>{value}</strong></div>;
}

function PeriodModelRanking({ models }: { models: ModelUsageRecord[] }) {
  return <section className="section-block analytics-model-ranking" aria-labelledby="period-model-ranking-heading"><div className="section-heading"><div><h2 id="period-model-ranking-heading">Top models this period</h2><p>Ranked using only the selected analytics window.</p></div></div>{models.length ? <div className="table-scroll"><table><thead><tr><th>Model</th><th>Provider</th><th>Requests</th><th>Tokens</th><th>Estimated spend</th></tr></thead><tbody>{models.map((model) => <tr key={`${model.providerName}\u0000${model.modelId}`}><td><strong className="mono">{model.providerName} / {model.modelId}</strong></td><td>{model.providerName}</td><td>{count(model.requests)}</td><td>{model.totalTokens == null ? "Not reported" : count(model.totalTokens)}</td><td>{model.estimatedSpendUsd == null ? "Not reported" : formatUsdExact(model.estimatedSpendUsd)}</td></tr>)}</tbody></table></div> : <div className="empty-state empty-compact"><div><h3>No model usage in this period</h3><p>Model rankings appear after requests are recorded.</p></div></div>}</section>;
}

function periodLabel(analytics: DashboardAnalytics): string {
  const from = new Date(analytics.window.from);
  const to = new Date(analytics.window.to);

  if (analytics.window.range === "current_month") return new Intl.DateTimeFormat("en-GB", { month: "long", year: "numeric", timeZone: analytics.window.timezone }).format(from);

  const formatter = new Intl.DateTimeFormat("en-GB", { day: "numeric", month: "short", timeZone: analytics.window.timezone });

  return `${formatter.format(from)} – ${formatter.format(to)}`;
}
