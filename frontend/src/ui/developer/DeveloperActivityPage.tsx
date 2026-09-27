import { useEffect, useState } from "react";
import { Activity, Search } from "lucide-react";
import type { ActivityEvent, ApiKeyRecord, DeveloperActivityFilter, Page, PortalApi } from "../../contracts/api";
import { formatUsd } from "../../lib/money";
import { getLayoutPreviewRole } from "../../lib/preview";

export function DeveloperActivityPage({ portalApi }: { portalApi: PortalApi }) {
  const [rows, setRows] = useState<ActivityEvent[]>([]);
  const [nextCursor, setNextCursor] = useState<string | null>(null);
  const [filters, setFilters] = useState<DeveloperActivityFilter>({ limit: 50 });
  const [keys, setKeys] = useState<ApiKeyRecord[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {

    if (getLayoutPreviewRole() === "developer") { setKeys([]); return; }

    void portalApi.listKeys().then(setKeys).catch(() => setKeys([]));
  }, [portalApi]);

  useEffect(() => {
    let active = true;
    setLoading(true);
    setError("");

    if (getLayoutPreviewRole() === "developer") {
      setRows([]);
      setNextCursor(null);
      setLoading(false);

      return () => { active = false; };
    }

    portalApi.listActivity(filters).then((page: Page<ActivityEvent>) => {
      if (active) {
        setRows((current) => filters.cursor ? [...current, ...page.items] : page.items);
        setNextCursor(page.nextCursor);
      }
    }).catch(() => { if (active) setError("Your request history could not be loaded. Retry or contact the operator."); })
      .finally(() => { if (active) setLoading(false); });

    return () => { active = false; };
  }, [portalApi, filters]);

  function changeFilter(key: keyof DeveloperActivityFilter, value: string) {
    setRows([]);
    setNextCursor(null);
    setFilters((current) => ({ ...current, cursor: undefined, [key]: value || undefined }));
  }

  return <>
    <header className="page-header"><div><h1>Activity</h1><p>Your request history only. Prompts and completions are never stored.</p></div></header>
    {error && <div className="inline-notice notice-error" role="alert">{error} <button type="button" className="button button-small" onClick={() => { setFilters((current) => ({ ...current, cursor: undefined })); }}>Retry</button></div>}
    <section className="section-block table-section"><div className="toolbar activity-toolbar developer-activity-filters">
      <label className="search-field"><Search size={16} aria-hidden="true" /><span className="sr-only">Filter by model</span><input value={filters.model ?? ""} onChange={(event) => changeFilter("model", event.target.value)} placeholder="Filter by model" /></label>
      <label className="select-filter"><span className="sr-only">Filter by key</span><select aria-label="Filter by key" value={filters.keyId ?? ""} onChange={(event) => changeFilter("keyId", event.target.value)}><option value="">All my keys</option>{keys.map((key) => <option key={key.id} value={key.id}>{key.label}</option>)}</select></label>
      <label className="select-filter"><span className="sr-only">Filter by result</span><select aria-label="Filter by result" value={filters.outcome ?? ""} onChange={(event) => changeFilter("outcome", event.target.value)}><option value="">All results</option><option value="success">Success</option><option value="error">Error</option><option value="rejected">Rejected</option><option value="interrupted">Interrupted</option></select></label>
      <label className="date-filter"><span>From</span><input aria-label="From date" type="date" value={filters.from ?? ""} onChange={(event) => changeFilter("from", event.target.value)} /></label>
      <label className="date-filter"><span>To</span><input aria-label="To date" type="date" value={filters.to ?? ""} onChange={(event) => changeFilter("to", event.target.value)} /></label>
      <span className="filter-note">Filters run on your account’s history</span>
    </div>
      {loading && rows.length === 0 ? <div className="loading-line" role="status"><span className="sr-only">Loading your activity</span></div> : rows.length ? <div className="table-scroll activity-table-wrap"><table><thead><tr><th>Request</th><th>Time</th><th>Provider / model</th><th>Key</th><th>Input</th><th>Output</th><th>Total</th><th>Cost</th><th>Result / latency</th></tr></thead><tbody>{rows.map((row) => <tr key={row.id}><td><code>{row.requestId ?? row.id}</code></td><td><time dateTime={row.occurredAt}>{new Intl.DateTimeFormat("en-GB", { dateStyle: "medium", timeStyle: "short", timeZone: "Europe/Berlin" }).format(new Date(row.occurredAt))}</time></td><td><strong>{row.providerName}</strong><small className="mono">{row.modelId}</small></td><td>{row.keyLabel}</td><td>{tokenCount(row.inputTokens)}</td><td>{tokenCount(row.outputTokens)}</td><td>{row.totalTokens == null ? "Not reported" : `${row.totalTokens.toLocaleString()} tokens`}{row.cachedTokens == null ? "" : <small>{row.cachedTokens.toLocaleString()} cached input</small>}</td><td>{row.estimatedCostUsd == null ? "Not reported" : formatUsd(row.estimatedCostUsd)}<small>{row.costSource === "gateway_estimate" ? "Local estimate" : "Cost unknown"}</small></td><td><span className={`status-label status-${row.status}`}>{row.status}</span><small>{row.latencyMs == null ? "Latency not reported" : `${row.latencyMs.toLocaleString()} ms`}</small></td></tr>)}</tbody></table></div> : <div className="empty-state"><span className="empty-mark"><Activity size={18} /></span><div><h3>{error ? "Activity unavailable" : "No requests match"}</h3><p>{error ? "Retry the owner-scoped request query." : "Adjust the server-side filters or wait for recorded gateway requests."}</p></div></div>}
      {!loading && nextCursor && <div className="load-more-row"><span className="muted-copy">More of your request history is available.</span><button type="button" className="button button-secondary" onClick={() => setFilters((current) => ({ ...current, cursor: nextCursor }))}>Load more</button></div>}
    </section>
  </>;
}

function tokenCount(value: number | null): string {
  return value == null ? "Not reported" : `${value.toLocaleString()} tokens`;
}
