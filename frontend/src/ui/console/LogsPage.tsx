import { useMemo, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { ListFilter } from "lucide-react";
import { api } from "../../lib/api";
import type { ActivityEvent } from "../../contracts/api";
import { count, dateTime } from "../../lib/format";
import { formatUsd } from "../../lib/money";
import { useLoad, DataNotice, EmptyState, LoadingLine, PageHeader, StatusLabel } from "../shared";
import { SelectMenu } from "../SelectMenu";

const ALL = "__all__";

interface LogsPageProps {
  operator?: boolean;
  title: string;
  description: string;
}

/** Metadata-only request log with a right-hand inspector. Prompts and responses
 * are never persisted by the gateway, so the inspector shows them as Not stored. */
export function LogsPage({ operator = false, title, description }: LogsPageProps) {
  const [searchParams, setSearchParams] = useSearchParams();
  const statusFilter = searchParams.get("status") ?? "";
  const modelFilter = searchParams.get("model") ?? "";
  const outcomeParam = statusFilter;

  const filters = useMemo(() => ({
    outcome: outcomeParam || undefined,
    model: modelFilter || undefined,
    limit: 100,
  }), [outcomeParam, modelFilter]);

  const load = useLoad(
    () => (operator ? api.listOperatorActivity(filters) : api.listActivity(filters)),
    [outcomeParam, modelFilter, operator],
  );
  const [selectedId, setSelectedId] = useState<string | null>(null);

  const rows = load.value?.items ?? [];
  const selected = rows.find((row) => row.id === selectedId) ?? null;

  function updateFilter(key: "status" | "model", value: string) {
    const next = new URLSearchParams(searchParams);
    if (value) next.set(key, value);
    else next.delete(key);
    setSearchParams(next, { replace: true });
    setSelectedId(null);
  }

  return <section className="page logs-page" aria-label={title}>
    <PageHeader title={title} description={description} action={<span className="logs-count mono">{rows.length} events</span>} />
    <DataNotice error={load.error} onRetry={load.reload} developer={operator} />
    <div className="logs-filter-bar" role="group" aria-label="Log filters">
      <ListFilter size={15} aria-hidden="true" />
      <SelectMenu
        ariaLabel="Filter by outcome"
        value={statusFilter || ALL}
        onValueChange={(value) => updateFilter("status", value === ALL ? "" : value)}
        options={[
          { value: ALL, label: "All outcomes" },
          { value: "success", label: "Success" },
          { value: "error", label: "Error" },
          { value: "rejected", label: "Rejected" },
          { value: "interrupted", label: "Interrupted" },
        ]}
      />
      <label className="logs-model-filter">
        <span className="sr-only">Filter by model</span>
        <input
          className="text-input"
          placeholder="Model contains…"
          defaultValue={modelFilter}
          onBlur={(event) => updateFilter("model", event.target.value.trim())}
          onKeyDown={(event) => {
            if (event.key === "Enter") updateFilter("model", (event.target as HTMLInputElement).value.trim());
          }}
        />
      </label>
    </div>
    <div className="logs-layout">
      <div className="logs-table-pane table-scroll" tabIndex={0} role="region" aria-label="Request log">
        {load.loading ? <LoadingLine /> : rows.length === 0
          ? <EmptyState title="No matching requests" body="No request events match the current filters. Usage is recorded for real traffic only." compact developer />
          : <table className="logs-table">
              <thead>
                <tr>
                  <th scope="col">Time</th>
                  <th scope="col">Model</th>
                  {!operator && <th scope="col">Key</th>}
                  {operator && <th scope="col">User</th>}
                  <th scope="col">Provider</th>
                  <th scope="col">Status</th>
                  <th scope="col" className="numeric">Tokens</th>
                  <th scope="col" className="numeric">Cost</th>
                  <th scope="col" className="numeric">Latency</th>
                </tr>
              </thead>
              <tbody>
                {rows.map((row) => <tr
                  key={row.id}
                  className={row.id === selectedId ? "is-selected" : undefined}
                  onClick={() => setSelectedId(row.id)}
                  onKeyDown={(event) => { if (event.key === "Enter") setSelectedId(row.id); }}
                  tabIndex={0}
                  aria-selected={row.id === selectedId}
                >
                  <td className="mono">{dateTime(row.occurredAt)}</td>
                  <td className="mono">{row.modelId}</td>
                  {!operator && <td>{row.keyLabel || "—"}</td>}
                  {operator && <td><OperatorOwnerCell row={row} /></td>}
                  <td>{row.providerName || "—"}</td>
                  <td><StatusLabel status={row.status} /></td>
                  <td className="numeric mono">{row.totalTokens == null ? "—" : count(row.totalTokens)}</td>
                  <td className="numeric mono">{row.estimatedCostUsd == null ? "—" : formatUsd(row.estimatedCostUsd)}</td>
                  <td className="numeric mono">{row.latencyMs == null ? "—" : `${count(row.latencyMs)} ms`}</td>
                </tr>)}
              </tbody>
            </table>}
      </div>
      <aside className="logs-inspector" aria-label="Request inspector">
        {selected
          ? <RequestInspector row={selected} operator={operator} />
          : <EmptyState compact developer title="Select a request" body="Pick a row to inspect its routing path, tokens, cost, and status." />}
      </aside>
    </div>
  </section>;
}

function OperatorOwnerCell({ row }: { row: ActivityEvent }) {
  const owner = (row as ActivityEvent & { ownerName?: string | null }).ownerName;
  const email = (row as ActivityEvent & { ownerEmail?: string | null }).ownerEmail;
  return <span>{owner || "Unknown"}<small>{email ?? ""}</small></span>;
}

function RequestInspector({ row, operator }: { row: ActivityEvent; operator: boolean }) {
  const [tab, setTab] = useState<"overview" | "routing" | "metadata">("overview");

  return <div className="inspector-body">
    <header className="inspector-header">
      <h2>Request</h2>
      <StatusLabel status={row.status} />
    </header>
    <div className="inspector-tabs" role="tablist" aria-label="Inspector sections">
      {(["overview", "routing", "metadata"] as const).map((value) => <button
        key={value}
        type="button"
        role="tab"
        aria-selected={tab === value}
        className={tab === value ? "is-active" : undefined}
        onClick={() => setTab(value)}
      >{value === "overview" ? "Overview" : value === "routing" ? "Routing" : "Metadata"}</button>)}
    </div>
    {tab === "overview" && <div className="inspector-section">
      <dl className="inspector-list">
        <div><dt>Time</dt><dd className="mono">{dateTime(row.occurredAt)}</dd></div>
        <div><dt>Model</dt><dd className="mono">{row.modelId}</dd></div>
        <div><dt>Provider</dt><dd>{row.providerName || "—"}</dd></div>
        {operator && <div><dt>Owner</dt><dd>{(row as ActivityEvent & { ownerName?: string | null }).ownerName ?? "Unknown"}</dd></div>}
        <div><dt>Tokens in / out</dt><dd className="mono">{row.inputTokens == null && row.outputTokens == null ? "Not reported" : `${count(row.inputTokens)} / ${count(row.outputTokens)}`}</dd></div>
        {row.cachedTokens != null && <div><dt>Cached input</dt><dd className="mono">{count(row.cachedTokens)}</dd></div>}
        <div><dt>Cost</dt><dd>{row.estimatedCostUsd == null ? "Unknown" : formatUsd(row.estimatedCostUsd)}<small>{row.costSource === "gateway_estimate" ? " · gateway estimate" : row.costSource === "provider_reported" ? " · provider reported" : " · cost unknown"}</small></dd></div>
        <div><dt>Latency</dt><dd className="mono">{row.latencyMs == null ? "Not reported" : `${count(row.latencyMs)} ms`}</dd></div>
        {row.errorCategory && <div><dt>Error</dt><dd className="mono">{row.errorCategory}</dd></div>}
      </dl>
    </div>}
    {tab === "routing" && <div className="inspector-section">
      <ol className="routing-path">
        <li><span>Router</span><small>Sponsored gateway</small></li>
        <li><span>Provider</span><small>{row.providerName || "Unknown provider"}</small></li>
        <li><span>Model</span><small className="mono">{row.modelId}</small></li>
      </ol>
      <p className="small muted">The gateway selects the highest-priority eligible route at request time; fallbacks apply only when a provider is known unreachable.</p>
    </div>}
    {tab === "metadata" && <div className="inspector-section">
      <dl className="inspector-list">
        <div><dt>Request ID</dt><dd className="mono">{row.requestId ?? "Not recorded"}</dd></div>
        <div><dt>Record ID</dt><dd className="mono">{row.id}</dd></div>
        {"requestIp" in row && row.requestIp != null && <div><dt>Client IP</dt><dd className="mono">{row.requestIp}</dd></div>}
        <div><dt>Token completeness</dt><dd>{row.tokenCompleteness ?? "unknown"}</dd></div>
      </dl>
      <div className="inspector-notstored">
        <p><strong>Prompt</strong><span>Not stored</span></p>
        <p><strong>Response</strong><span>Not stored</span></p>
      </div>
    </div>}
  </div>;
}
