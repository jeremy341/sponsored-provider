import { useEffect, useState } from "react";
import { Activity, Search } from "lucide-react";
import type { ActivityEvent, Page, PortalApi } from "../../contracts/api";
import { formatUsd } from "../../lib/money";

export function DeveloperActivityPage({ portalApi }: { portalApi: PortalApi }) {
  const [rows, setRows] = useState<ActivityEvent[]>([]);
  const [cursor, setCursor] = useState<string | undefined>();
  const [nextCursor, setNextCursor] = useState<string | null>(null);
  const [model, setModel] = useState("");
  const [status, setStatus] = useState("all");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    let active = true;
    setLoading(true);
    setError("");

    portalApi.listActivity(cursor).then((page: Page<ActivityEvent>) => {
      if (active) {
        setRows((current) => cursor ? [...current, ...page.items] : page.items);
        setNextCursor(page.nextCursor);
      }
    }).catch(() => { if (active) setError("Your request history could not be loaded. Retry or contact the operator."); })
      .finally(() => { if (active) setLoading(false); });

    return () => { active = false; };
  }, [portalApi, cursor]);

  const visible = rows.filter((row) => (!model || row.modelId.toLowerCase().includes(model.toLowerCase())) && (status === "all" || row.status === status));

  return <>
    <header className="page-header"><div><h1>Activity</h1><p>Your request history only. Prompts and completions are never stored.</p></div></header>
    {error && <div className="inline-notice notice-error" role="alert">{error} <button type="button" className="button button-small" onClick={() => { setCursor(undefined); setRows([]); }}>Retry</button></div>}
    <section className="section-block table-section"><div className="toolbar activity-toolbar"><label className="search-field"><Search size={16} aria-hidden="true" /><span className="sr-only">Filter by model</span><input value={model} onChange={(event) => setModel(event.target.value)} placeholder="Filter by model" /></label><label className="select-filter"><span className="sr-only">Filter by result</span><select aria-label="Filter by result" value={status} onChange={(event) => setStatus(event.target.value)}><option value="all">All results</option><option value="success">Success</option><option value="error">Error</option><option value="rejected">Rejected</option><option value="interrupted">Interrupted</option></select></label><span className="filter-note">Only your keys and requests</span></div>
      {loading && rows.length === 0 ? <div className="loading-line" role="status"><span className="sr-only">Loading your activity</span></div> : visible.length ? <div className="table-scroll activity-table-wrap"><table><thead><tr><th>Request</th><th>Time</th><th>Provider / model</th><th>Key</th><th>Input / output</th><th>Cost</th><th>Result / latency</th></tr></thead><tbody>{visible.map((row) => <tr key={row.id}><td><code>{row.requestId ?? row.id}</code></td><td><time dateTime={row.occurredAt}>{new Intl.DateTimeFormat("en-GB", { dateStyle: "medium", timeStyle: "short", timeZone: "Europe/Berlin" }).format(new Date(row.occurredAt))}</time></td><td><strong>{row.providerName}</strong><small className="mono">{row.modelId}</small></td><td>{row.keyLabel}</td><td>{row.inputTokens == null ? "Not reported" : row.inputTokens.toLocaleString()} / {row.outputTokens == null ? "Not reported" : row.outputTokens.toLocaleString()}<small>{row.totalTokens == null ? "Total not reported" : `${row.totalTokens.toLocaleString()} total`}{row.cachedTokens == null ? "" : ` · ${row.cachedTokens.toLocaleString()} cached`}</small></td><td>{row.estimatedCostUsd == null ? "Not reported" : formatUsd(row.estimatedCostUsd)}<small>{row.costSource === "gateway_estimate" ? "Local estimate" : "Cost unknown"}</small></td><td><span className={`status-label status-${row.status}`}>{row.status}</span><small>{row.latencyMs == null ? "Latency not reported" : `${row.latencyMs.toLocaleString()} ms`}</small></td></tr>)}</tbody></table></div> : <div className="empty-state"><span className="empty-mark"><Activity size={18} /></span><div><h3>{error ? "Activity unavailable" : rows.length ? "No requests match" : "No requests yet"}</h3><p>{rows.length ? "Change the model or result filter." : "Requests from your API keys appear here with reported tokens and latency."}</p></div></div>}
      {!loading && nextCursor && <div className="load-more-row"><span className="muted-copy">More of your request history is available.</span><button type="button" className="button button-secondary" disabled={loading} onClick={() => setCursor(nextCursor)}>Load more</button></div>}
    </section>
  </>;
}
