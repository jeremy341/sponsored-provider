import { CircleSlash, Gauge, HeartPulse, Boxes } from "lucide-react";
import { apiExtensions } from "../../lib/api";
import { count, dateTime } from "../../lib/format";
import { DataNotice, EmptyState, LoadingLine, PageHeader, StatusLabel, useLoad } from "../shared";

function formatPercent(value: number | null): string {
  return value == null ? "Unknown" : `${(value * 100).toFixed(1)}%`;
}

function formatLatency(value: number | null): string {
  return value == null ? "Unknown" : `${count(value)} ms`;
}

/** Developer-facing provider transparency: measured health only — never
 * credentials, funding, or operator configuration. */
export function DeveloperProvidersPage() {
  const load = useLoad(() => apiExtensions.listDeveloperProviders(), []);

  return <section className="page providers-dev-page" aria-label="Providers">
    <PageHeader
      title="Providers"
      description="Measured health of the providers behind the gateway, computed from real request outcomes over the last 14 days."
      action={<span className="inline-notice notice-info"><HeartPulse size={15} /><span>Read-only</span></span>}
    />
    <DataNotice error={load.error} onRetry={load.reload} developer />
    {load.loading ? <LoadingLine /> : !load.value?.length
      ? <EmptyState title="No provider activity yet" body="Providers appear here once the operator enables routes and real traffic flows." developer />
      : <div className="provider-health-grid" role="list">
          {load.value.map((provider) => <article className="provider-health-card" role="listitem" key={provider.provider}>
            <header className="provider-health-header">
              <h2>{provider.provider}</h2>
              <StatusLabel status={provider.health} />
            </header>
            <div className="provider-health-metrics">
              <span><small>Success rate</small><strong>{formatPercent(provider.successRate)}</strong></span>
              <span><small>p50 latency</small><strong>{formatLatency(provider.p50LatencyMs)}</strong></span>
              <span><small>p95 latency</small><strong>{formatLatency(provider.p95LatencyMs)}</strong></span>
              <span><small>Models</small><strong>{count(provider.models)}</strong></span>
            </div>
            <footer className="provider-health-foot">
              <Gauge size={14} aria-hidden="true" />
              {provider.sampleSize < 5
                ? <span className="muted">No recent traffic — health becomes measurable after more routed requests.</span>
                : <span className="muted">{count(provider.sampleSize)} routed requests · last activity {provider.lastActivityAt ? dateTime(provider.lastActivityAt) : "unknown"}</span>}
            </footer>
          </article>)}
        </div>}
    <p className="small muted provider-privacy-note"><CircleSlash size={14} aria-hidden="true" /> Provider credentials, funding, and routing configuration are operator-managed and not visible here.</p>
    <p className="small muted"><Boxes size={14} aria-hidden="true" /> Unknown health means insufficient recent samples — never a synthetic score.</p>
  </section>;
}
