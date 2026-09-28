import { useEffect, useState } from "react";
import { NavLink } from "react-router-dom";
import { ArrowRight, Boxes, CircleHelp, ShieldAlert } from "lucide-react";
import { formatUsd } from "../lib/money";
import { count, dateTime, money, tokens } from "../lib/format";
import { getLayoutPreviewRole } from "../lib/preview";
import type { ActivityEvent, ModelUsageRecord, UsageSummary } from "../contracts/api";

export interface LoadResult<T> {
  value: T | null;
  error: string | null;
  loading: boolean;
  reload: () => void;
}

export function PageHeader({ title, description, action }: { title: string; description: string; action?: React.ReactNode }) {
  return <header className="page-header"><div><h1>{title}</h1><p>{description}</p></div>{action && <div className="page-header-action">{action}</div>}</header>;
}

export function LoadingLine() {
  return <div className="loading-line" role="status"><span className="sr-only">Loading</span></div>;
}

export function StatusLabel({ status }: { status: string }) {
  const safeStatus = status.toLowerCase();

  return <span className={`status-label status-${safeStatus}`}><span className="status-dot" aria-hidden="true" />{status.replaceAll("_", " ")}</span>;
}

export function DataNotice({ error, onRetry, developer = false }: { error: string | null; onRetry?: () => void; developer?: boolean }) {
  if (!error) return null;

  return <div className={`inline-notice notice-error${developer ? " developer-notice" : " operator-notice"}`} role="alert"><ShieldAlert size={17} /><span>{error}</span>{onRetry && <button type="button" className="button button-small" onClick={onRetry}>Retry</button>}</div>;
}

export function EmptyState({ title, body, action, compact = false, developer = false }: { title: string; body: string; action?: React.ReactNode; compact?: boolean; developer?: boolean }) {
  return <div className={`empty-state${compact ? " empty-compact" : ""}${developer ? " empty-developer" : " empty-operator"}`}><span className="empty-mark"><CircleHelp size={19} /></span><div><h3>{title}</h3><p>{body}</p>{action && <div className="empty-action">{action}</div>}</div></div>;
}

export function StatStrip({ usage, developer = false }: { usage: UsageSummary | null; developer?: boolean }) {
  if (!usage) return <section className="lifetime-summary" aria-label="Lifetime usage"><span className="eyebrow">Lifetime</span><EmptyState title="Usage data isn’t connected" body="No usage figures are available from the portal API yet. This view will never substitute sample numbers." compact developer={developer} /></section>;

  const rows = [
    ["Requests", count(usage.requests), `${count(usage.successfulRequests)} successful · ${count(usage.rejectedRequests)} rejected`],
    ["Input / output", `${count(usage.inputTokens)} / ${count(usage.outputTokens)}`, "Reported tokens"],
    ["Total tokens", tokens(usage.totalTokens), "Reported total"],
    ["Estimated spend", usage.estimatedSpendUsd == null ? "Not reported" : formatUsd(usage.estimatedSpendUsd), usage.source === "provider_reported" ? "Provider reported" : usage.source === "mixed" ? "Mixed source" : "Gateway estimate"],
  ];

  return <section className="lifetime-summary" aria-label="Lifetime usage"><span className="eyebrow">Lifetime totals</span><div className="stat-strip" aria-label="Lifetime usage summary">{rows.map(([label, value, context], index) => <div className={`stat-cell${index === 0 ? " stat-cell-primary" : ""}`} key={label}><span>{label}</span><strong>{value}</strong><small>{context}</small></div>)}</div></section>;
}

export function AllowanceRunway({ allowance }: { allowance: { usedUsd: number | null; limitUsd: number | null; period: string | null; resetAt: string | null } | null }) {
  const percent = allowance?.usedUsd != null && allowance.limitUsd != null && allowance.limitUsd > 0 ? Math.min(100, allowance.usedUsd / allowance.limitUsd * 100) : null;

  return <div className="runway"><div className="runway-values"><span>{allowance?.usedUsd == null ? "Usage not reported" : `${money(allowance.usedUsd)} used`}</span><strong>{allowance?.limitUsd == null ? "Limit not assigned" : `${money(allowance.limitUsd)} ${allowance.period ?? "period"}`}</strong></div><div className="runway-track" role="progressbar" aria-label="Allowance used" aria-valuemin={0} aria-valuemax={100} aria-valuenow={percent == null ? undefined : Math.round(percent)}><span style={{ transform: `scaleX(${percent == null ? 0 : percent / 100})` }} /></div><p>{allowance?.resetAt ? `Resets ${dateTime(allowance.resetAt)}` : "Reset schedule unavailable"}</p></div>;
}

export function ModelUsagePanel({ models, loading, developer = false }: { models: ModelUsageRecord[]; loading: boolean; developer?: boolean }) {
  return <section className="section-block"><div className="section-heading"><div><h2>Lifetime models in use</h2><p>All-time request count, reported tokens, and recorded cost.</p></div><Boxes size={18} /></div>{loading ? <LoadingLine /> : models.length ? <div className="table-scroll" tabIndex={0} role="region" aria-label="Lifetime models in use"><table><thead><tr><th scope="col">Model</th><th scope="col">Provider</th><th scope="col">Requests</th><th scope="col">Tokens</th><th scope="col">Estimated spend</th></tr></thead><tbody>{models.map((model) => <tr key={`${model.providerName}\u0000${model.modelId}`}><td><strong className="mono">{model.modelId}</strong></td><td>{model.providerName}</td><td>{count(model.requests)}</td><td>{model.totalTokens == null ? "Not reported" : count(model.totalTokens)}</td><td>{model.estimatedSpendUsd == null ? "Not reported" : formatUsd(model.estimatedSpendUsd)}</td></tr>)}</tbody></table></div> : <EmptyState title="No model usage yet" body="Real requests will add models here. No sample usage is shown." compact developer={developer} />}</section>;
}

export function ActivityTable({ rows, developer }: { rows: ActivityEvent[]; developer: boolean }) {
  return <div className="table-scroll activity-table-wrap" tabIndex={0} role="region" aria-label="Recent activity"><table><thead><tr><th scope="col">Time</th><th scope="col">Model</th><th scope="col">Tokens in / out</th><th scope="col">Cost</th><th scope="col">Result</th><th scope="col">Latency</th>{!developer && <th scope="col">Client IP</th>}</tr></thead><tbody>{rows.map((row) => <tr key={row.id}><td>{dateTime(row.occurredAt)}</td><td><strong className="mono">{row.modelId}</strong><small>{row.keyLabel}</small></td><td>{row.inputTokens == null && row.outputTokens == null ? "Usage not reported" : `${count(row.inputTokens)} / ${count(row.outputTokens)}`}<small>{row.totalTokens == null ? "Total not reported" : `${count(row.totalTokens)} total`}{row.cachedTokens != null ? ` · ${count(row.cachedTokens)} cached` : ""}</small></td><td>{row.estimatedCostUsd == null ? "Not reported" : formatUsd(row.estimatedCostUsd)}<small>{row.costSource === "gateway_estimate" ? "Gateway estimate" : row.costSource === "provider_reported" ? "Provider-reported" : "Cost unknown"}</small></td><td><StatusLabel status={row.status} />{row.errorCategory && <small>{row.errorCategory}</small>}</td><td>{row.latencyMs == null ? "Not reported" : `${count(row.latencyMs)} ms`}</td>{!developer && <td className="mono">{row.requestIp ?? "Not recorded"}</td>}</tr>)}</tbody></table></div>;
}

export function ActivitySection({ rows, loading, error, developer = false }: { rows: ActivityEvent[]; loading: boolean; error: string | null; developer?: boolean }) {
  return <section className="section-block activity-preview"><div className="section-heading"><div><h2>Recent activity</h2><p>{developer ? "Your latest requests" : "Latest gateway requests"}</p></div><NavLink to={developer ? "/developer/activity" : "/operator/usage"} className="text-link">View activity <ArrowRight size={15} /></NavLink></div>
    {loading ? <LoadingLine /> : rows.length ? <ActivityTable rows={rows.slice(0, 6)} developer={developer} /> : <EmptyState title={error ? "Activity unavailable" : "No recent activity"} body={error ? "The API could not load activity records." : "No request events have been returned for this period."} compact developer={developer} />}
  </section>;
}

export function useLoad<T>(loader: () => Promise<T>, dependencies: React.DependencyList = []): LoadResult<T> {
  const [value, setValue] = useState<T | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [reloadIndex, setReloadIndex] = useState(0);
  const reload = () => setReloadIndex((previous) => previous + 1);
  const previewRole = getLayoutPreviewRole();

  useEffect(() => {
    if (previewRole) {
      setValue(null);
      setError(null);
      setLoading(false);

      return;
    }

    let active = true;
    setLoading(true);
    setError(null);

    async function fetchPage() {
      try {
        const result = await loader();

        if (active) setValue(result);
      } catch {
        if (active) setError("The portal API could not load this data. Retry or contact the operator.");
      } finally {
        if (active) setLoading(false);
      }
    }

    void fetchPage();

    return () => { active = false; };
  // SAFETY: callers pass explicit dependency tuples; previewRole and reloadIndex gate refetching.
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [...dependencies, previewRole, reloadIndex]);

  return { value, error, loading, reload };
}
