import { useState } from "react";
import { NavLink } from "react-router-dom";
import { ArrowRight, Clock3, Network, Wallet } from "lucide-react";
import { api } from "../../lib/api";
import { count, dateTime, money } from "../../lib/format";
import type { DashboardRange, ProviderRecord } from "../../contracts/api";
import { ActivitySection, AllowanceRunway, DataNotice, EmptyState, LoadingLine, ModelUsagePanel, PageHeader, StatStrip, StatusLabel, useLoad } from "../shared";
import { DashboardAnalyticsPanel } from "../DashboardAnalyticsPanel";

export function OperatorOverview() {
  const [range, setRange] = useState<DashboardRange>("current_month");
  const data = useLoad(() => api.getOperatorDashboard(range), [range]);
  const dash = data.value;

  return <>
    <PageHeader title="Overview" description="Protect the shared upstream budget and see what needs attention." action={<span className="period-chip"><Clock3 size={14} /> Current period</span>} />
    <DataNotice error={data.error} onRetry={data.reload} />
    {data.loading ? <LoadingLine /> : <StatStrip usage={dash?.usage ?? null} />}
    <div className="content-grid operator-grid">
      <section className="section-block runway-block"><div className="section-heading"><div><h2>Global usage runway</h2><p>Local estimate plus active reservations when provided by the API.</p></div><Wallet size={18} /></div><AllowanceRunway allowance={dash?.guardrails ? { usedUsd: dash.guardrails.globalSpendUsedUsd, limitUsd: dash.guardrails.globalSpendCapUsd, period: "global cap", resetAt: null } : null} />{dash?.guardrails && <p className="source-note">Safety reserve: {money(dash.guardrails.safetyReserveUsd)} · {dash.guardrails.globalStopped ? "Global stop is active" : "Global stop is not active"}</p>}</section>
      <section className="section-block"><div className="section-heading"><div><h2>Provider health</h2><p>Connection and model-catalog freshness.</p></div><NavLink to="/operator/providers" className="text-link">Manage <ArrowRight size={15} /></NavLink></div>{data.loading ? <LoadingLine /> : dash?.providers.length ? <ProviderList providers={dash.providers} /> : <EmptyState title="No provider status available" body="Connectors will be listed after the operator API returns provider health." compact />}</section>
      <ActivitySection rows={dash?.recentActivity ?? []} loading={data.loading} error={data.error} />
    </div>
    <DashboardAnalyticsPanel analytics={dash?.analytics ?? null} range={range} onRangeChange={setRange} loading={data.loading} />
    <ModelUsagePanel models={dash?.topModels ?? []} loading={data.loading} />
  </>;
}

function ProviderList({ providers }: { providers: ProviderRecord[] }) {
  return <div className="provider-list">{providers.map((provider) => <div className="provider-row" key={provider.id}><span className="provider-icon"><Network size={17} /></span><div className="provider-copy"><strong>{provider.name}</strong><small className="mono">{provider.baseUrlDisplay}</small></div><div className="provider-model-count">{count(provider.approvedModels)} / {count(provider.discoveredModels)} models approved</div><StatusLabel status={provider.health} /><span className="provider-sync">{provider.lastSyncAt ? `Synced ${dateTime(provider.lastSyncAt)}` : "Never synced"}</span></div>)}</div>;
}
