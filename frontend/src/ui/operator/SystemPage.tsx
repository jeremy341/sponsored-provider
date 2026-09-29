import { Database, HardDriveDownload, RefreshCw, ShieldCheck } from "lucide-react";
import { apiExtensions } from "../../lib/api";
import { count, dateTime } from "../../lib/format";
import { formatUsd } from "../../lib/money";
import { DataNotice, EmptyState, LoadingLine, PageHeader, StatusLabel, useLoad } from "../shared";

function formatBytes(bytes: number): string {
  if (!bytes) return "Unknown";
  const units = ["B", "KiB", "MiB", "GiB"];
  let value = bytes;
  let unit = 0;
  while (value >= 1024 && unit < units.length - 1) {
    value /= 1024;
    unit += 1;
  }
  return `${value.toFixed(value >= 10 || unit === 0 ? 0 : 1)} ${units[unit]}`;
}

function formatUptime(seconds: number): string {
  const days = Math.floor(seconds / 86400);
  const hours = Math.floor((seconds % 86400) / 3600);
  const minutes = Math.floor((seconds % 3600) / 60);
  return days ? `${days}d ${hours}h` : hours ? `${hours}h ${minutes}m` : `${minutes}m`;
}

/** Real operational facts only: version, uptime, database, job status.
 * No secrets, no SQL console, no casual restore actions. */
export function SystemPage() {
  const load = useLoad(() => apiExtensions.getOperatorSystem(), []);
  const snapshot = load.value;

  return <section className="page system-page" aria-label="System">
    <PageHeader
      title="System"
      description="Deployment facts and background job status. Values are read live from the running service."
    />
    <DataNotice error={load.error} onRetry={load.reload} />
    {load.loading ? <LoadingLine /> : !snapshot
      ? null
      : <>
          <div className="system-kpis">
            <article className="stat-card"><small>Version</small><strong className="mono">{snapshot.version}</strong><span className="muted">Python {snapshot.pythonVersion}</span></article>
            <article className="stat-card"><small>Uptime</small><strong className="mono">{formatUptime(snapshot.uptimeSeconds)}</strong><span className="muted">{snapshot.platform.split(" ").slice(0, 2).join(" ")}</span></article>
            <article className="stat-card">
              <small>Inference</small>
              <StatusLabel status={snapshot.inference.stopped ? "stopped" : "running"} />
              <span className="muted">{snapshot.inference.stopSource === "emergency_stop" ? "Emergency stop active (environment)" : snapshot.inference.stopSource === "operator_stop" ? "Operator stop active" : "Accepting sponsored requests"}</span>
            </article>
            <article className="stat-card"><small>Global spend cap</small><strong className="mono">{snapshot.inference.globalSpendCapUsd == null ? "Not set" : formatUsd(String(snapshot.inference.globalSpendCapUsd))}</strong><span className="muted">Reserve {snapshot.inference.safetyReserveUsd == null ? "not set" : formatUsd(String(snapshot.inference.safetyReserveUsd))}</span></article>
          </div>
          <div className="system-columns">
            <article className="section-block" aria-label="Database">
              <div className="section-heading"><div><h2><Database size={16} aria-hidden="true" /> Database</h2><p>Live engine facts from the open connection.</p></div></div>
              <dl className="inspector-list">
                <div><dt>Engine</dt><dd>{snapshot.database.engine} {snapshot.database.sqliteVersion}</dd></div>
                <div><dt>File</dt><dd className="mono">{snapshot.database.path ?? "in-memory"}</dd></div>
                <div><dt>Size</dt><dd className="mono">{formatBytes(snapshot.database.sizeBytes)}</dd></div>
                <div><dt>Tables</dt><dd className="mono">{count(snapshot.database.tableCount)}</dd></div>
                <div><dt>Schema version</dt><dd className="mono">{snapshot.database.schemaVersion}</dd></div>
              </dl>
            </article>
            <article className="section-block" aria-label="Jobs">
              <div className="section-heading"><div><h2><RefreshCw size={16} aria-hidden="true" /> Jobs</h2><p>Last runs observed by this deployment.</p></div></div>
              <dl className="inspector-list">
                <div><dt>Provider model sync</dt><dd>{snapshot.jobs.lastProviderSyncAt ? dateTime(snapshot.jobs.lastProviderSyncAt) : "Never run"}</dd></div>
                <div><dt>Backup</dt><dd>{snapshot.jobs.backupStatus === "not_configured" ? "Not configured" : snapshot.jobs.lastBackupAt ? dateTime(snapshot.jobs.lastBackupAt) : "Unknown"}</dd></div>
                <div><dt>Restore test</dt><dd>{snapshot.jobs.lastRestoreTestAt ? dateTime(snapshot.jobs.lastRestoreTestAt) : "Never run"}</dd></div>
              </dl>
              <p className="small muted"><HardDriveDownload size={14} aria-hidden="true" /> Backups and restore drills are deployment-level concerns; this console reports status only and never triggers restores.</p>
            </article>
            <article className="section-block" aria-label="Footprint">
              <div className="section-heading"><div><h2><ShieldCheck size={16} aria-hidden="true" /> Footprint</h2><p>Recorded volumes over all time (30 days for events).</p></div></div>
              <dl className="inspector-list">
                <div><dt>Users</dt><dd className="mono">{count(snapshot.counts.users)}</dd></div>
                <div><dt>Active API keys</dt><dd className="mono">{count(snapshot.counts.activeApiKeys)}</dd></div>
                <div><dt>Provider connections</dt><dd className="mono">{count(snapshot.counts.providerConnections)}</dd></div>
                <div><dt>Approved & active offers</dt><dd className="mono">{count(snapshot.counts.activeOffers)}</dd></div>
                <div><dt>Usage events (30d)</dt><dd className="mono">{count(snapshot.counts.usageEvents30d)}</dd></div>
              </dl>
            </article>
          </div>
        </>}
    {!load.loading && !snapshot && !load.error && <EmptyState title="System snapshot unavailable" body="The API returned no deployment facts." compact />}
  </section>;
}
