import { useEffect, useState } from "react";
import { Activity, Search } from "lucide-react";
import { SelectMenu } from "../../SelectMenu";
import { DashboardAnalyticsPanel } from "../../DashboardAnalyticsPanel";
import { useLoad } from "../../shared";
import { api } from "../../../lib/api";
import type { DashboardRange, OperatorActivityRecord, OperatorUsageFilter, Page, PortalApi, ProviderConnectionRecord } from "../../../contracts/api";
import { formatUsd } from "../../../lib/money";
import { getLayoutPreviewRole } from "../../../lib/preview";

export function OperatorUsagePage({ portalApi }: { portalApi: PortalApi }) {
  const [range, setRange] = useState<DashboardRange>("current_month");
  const previewing = getLayoutPreviewRole() === "operator";
  const dashboard = useLoad(() => (previewing ? Promise.resolve(null) : api.getOperatorDashboard(range)), [range, previewing]);
  const [providers, setProviders] = useState<ProviderConnectionRecord[]>([]);
  const [rows, setRows] = useState<OperatorActivityRecord[]>([]);
  const [nextCursor, setNextCursor] = useState<string | null>(null);
  const [filters, setFilters] = useState<OperatorUsageFilter>({ limit: 50 });
  const [loading, setLoading] = useState(true); const [error, setError] = useState("");
  useEffect(() => {

    if (getLayoutPreviewRole() === "operator") {
      setProviders([]);

      return;
    }

    void portalApi.listProviders().then(setProviders).catch(() => setProviders([]));
  }, [portalApi]);
  useEffect(() => {
    let current = true; setLoading(true); setError("");

    if (getLayoutPreviewRole() === "operator") {
      setRows([]);
      setNextCursor(null);
      setLoading(false);

      return () => { current = false; };
    }

    portalApi.listOperatorActivity(filters).then((page: Page<OperatorActivityRecord>) => { if (current) { setRows((existing) => filters.cursor ? [...existing, ...page.items] : page.items); setNextCursor(page.nextCursor); } })
      .catch(() => { if (current) setError("Usage could not be loaded with these filters. Adjust them or retry."); })
      .finally(() => { if (current) setLoading(false); });

    return () => { current = false; };
  }, [portalApi, filters]);

  function change(key: keyof OperatorUsageFilter, value: string) { setFilters((current) => ({ ...current, cursor: undefined, [key]: value || undefined })); }

  const brandOptions: Array<[string, string]> = [];
  providers.forEach((item) => { if (item.brandSlug !== null) brandOptions.push([item.brandSlug, item.brandName]); });

  return <><header className="page-header"><div><h1>Usage</h1><p>Period graphs first, then the full filterable request log.</p></div></header>
    <DashboardAnalyticsPanel analytics={dashboard.value?.analytics ?? null} range={range} onRangeChange={setRange} loading={dashboard.loading} />
    <section className="section-block table-section operator-usage-page"><div className="toolbar usage-filter-toolbar">
      <div className="select-filter"><SelectMenu ariaLabel="Provider brand" value={filters.brandSlug ?? "__all__"} onValueChange={(next) => change("brandSlug", next === "__all__" ? "" : next)} options={[{ value: "__all__", label: "All brands" }, ...brandOptions.map(([slug, name]) => ({ value: slug, label: name }))]} /></div>
      <div className="select-filter"><SelectMenu ariaLabel="Connection" value={filters.connectionId ?? "__all__"} onValueChange={(next) => change("connectionId", next === "__all__" ? "" : next)} options={[{ value: "__all__", label: "All connections" }, ...providers.filter((item) => !filters.brandSlug || item.brandSlug === filters.brandSlug).map((item) => ({ value: item.id, label: `${item.brandName} / ${item.connectionLabel}` }))]} /></div>
      <label className="search-field"><Search size={16} aria-hidden="true" /><span className="sr-only">Model</span><input aria-label="Model" value={filters.model ?? ""} onChange={(event) => change("model", event.target.value)} placeholder="Filter model" /></label>
      <label className="date-filter"><span>From</span><input aria-label="From date" type="date" value={filters.from ?? ""} onChange={(event) => change("from", event.target.value)} /></label>
      <label className="date-filter"><span>To</span><input aria-label="To date" type="date" value={filters.to ?? ""} onChange={(event) => change("to", event.target.value)} /></label>
      <div className="select-filter"><SelectMenu ariaLabel="Outcome" value={filters.outcome ?? "__all__"} onValueChange={(next) => change("outcome", next === "__all__" ? "" : next)} options={[{ value: "__all__", label: "All outcomes" }, { value: "success", label: "Success" }, { value: "error", label: "Error" }, { value: "rejected", label: "Rejected" }, { value: "interrupted", label: "Interrupted" }]} /></div>
    </div>
    {error && <p className="inline-notice notice-error" role="alert">{error} <button type="button" className="button button-small" onClick={() => setFilters((current) => ({ ...current }))}>Retry</button></p>}
    {loading && rows.length === 0 ? <div className="loading-line" role="status"><span className="sr-only">Loading usage</span></div> : rows.length ? <div className="table-scroll activity-table-wrap" tabIndex={0} role="region" aria-label="Operator usage events"><table><thead><tr><th scope="col">Request</th><th scope="col">Time</th><th scope="col">Provider / connection</th><th scope="col">Model</th><th scope="col">Input</th><th scope="col">Output</th><th scope="col">Total</th><th scope="col">Cost</th><th scope="col">Latency</th><th scope="col">Outcome</th></tr></thead><tbody>{rows.map((row) => <tr key={row.id}><td><code>{row.requestId ?? row.id}</code></td><td>{new Date(row.occurredAt).toLocaleString("en-GB", { timeZone: "Europe/Berlin" })}</td><td>{row.providerName}<small>{row.connectionLabel ?? "Connection not reported"}</small></td><td><strong className="mono">{row.modelId}</strong></td><td>{row.inputTokens == null ? "Not reported" : row.inputTokens.toLocaleString()}</td><td>{row.outputTokens == null ? "Not reported" : row.outputTokens.toLocaleString()}</td><td>{row.totalTokens == null ? "Not reported" : row.totalTokens.toLocaleString()}{row.cachedTokens != null && <small>{row.cachedTokens.toLocaleString()} cached</small>}</td><td>{row.estimatedCostUsd == null ? "Not reported" : formatUsd(row.estimatedCostUsd)}<small>{row.costSource === "provider_reported" ? "Provider reported" : row.costSource === "unknown" ? "Source unknown" : "Local estimate"}</small></td><td>{row.latencyMs == null ? "Not reported" : `${row.latencyMs} ms`}</td><td><span className={`status-label status-${row.status}`}>{row.status}</span></td></tr>)}</tbody></table></div> : <div className="empty-state"><span className="empty-mark"><Activity size={18} /></span><div><h3>No usage events match</h3><p>Adjust the server-side filters or wait for recorded gateway requests.</p></div></div>}
    {!loading && nextCursor && <div className="load-more-row"><span className="muted-copy">More matching events are available.</span><button className="button button-secondary" type="button" onClick={() => setFilters((current) => ({ ...current, cursor: nextCursor }))}>Load more</button></div>}
    </section></>;
}
