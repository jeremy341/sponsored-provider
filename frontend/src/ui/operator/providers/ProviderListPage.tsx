import { useEffect, useMemo, useState } from "react";
import { ChevronDown, Network, RefreshCw } from "lucide-react";
import type { PortalApi, ProviderConnectionRecord } from "../../../contracts/api";
import { getLayoutPreviewRole } from "../../../lib/preview";
import { DataNotice, LoadingLine, PageHeader } from "../../shared";
import { MoneyRunway } from "../MoneyRunway";
import { ConnectionBudgetEditor } from "./ConnectionBudgetEditor";
import { ConnectionDialog } from "./ConnectionDialog";

export function ProviderListPage({ portalApi }: { portalApi: PortalApi }) {
  const [providers, setProviders] = useState<ProviderConnectionRecord[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState("");
  const [syncing, setSyncing] = useState<string | null>(null);
  const [openBrands, setOpenBrands] = useState<Set<string>>(new Set());

  const refresh = () => {
    if (getLayoutPreviewRole() === "operator") {
      setProviders([]);
      setError(null);
      setLoading(false);

      return;
    }

    setLoading(true); setError(null);
    portalApi.listProviders().then((connections) => { setProviders(connections); setOpenBrands(new Set(connections.map((item) => item.brandSlug ?? `unmapped:${item.id}`))); })
      .catch(() => setError("Provider connections could not be loaded. Retry to refresh the list."))
      .finally(() => setLoading(false));
  };

  useEffect(refresh, [portalApi]);

  const groups = useMemo(() => {
    const map = new Map<string, { name: string; connections: ProviderConnectionRecord[] }>();
    providers.forEach((connection) => {
      const groupKey = connection.brandSlug ?? `unmapped:${connection.id}`;
      const name = connection.brandSlug ? connection.brandName : `${connection.brandName} · mapping required`;
      const group = map.get(groupKey) ?? { name, connections: [] };
      group.connections.push(connection);
      map.set(groupKey, group);
    });

    return [...map.entries()].map(([slug, group]) => ({ slug, ...group }));
  }, [providers]);

  async function sync(connection: ProviderConnectionRecord) {
    setSyncing(connection.id); setNotice("");

    try {
      const result = await portalApi.syncProvider(connection.id);

      const status = "tested" in result
        ? `Connection test: ${result.tested ? "passed" : "failed"}. Model discovery: ${result.error ? `failed — ${result.error}` : `${result.discovered} models found`}.`
        : `Sync complete: ${result.modelsDiscovered} models discovered${result.staleModels ? `; ${result.staleModels} prior models retained` : ""}.`;

      setNotice(status);
      refresh();
    }
    catch (caught) { setNotice(`Sync failed; existing models were preserved. ${caught instanceof Error ? caught.message : "Check the connection and retry."}`); }
    finally { setSyncing(null); }
  }

  return <>
    <PageHeader title="Providers" description="Manage upstream connections, credentials, sync, and connection budgets." action={<ConnectionDialog portalApi={portalApi} onCreated={(summary) => { setNotice(summary); refresh(); }} />} />
    {notice && <div className={`inline-notice ${notice.toLowerCase().includes("failed") ? "notice-error" : "notice-info"}`} role={notice.toLowerCase().includes("failed") ? "alert" : "status"}><Network size={16} /><span>{notice}</span></div>}
    <DataNotice error={error} onRetry={refresh} />
    {loading ? <LoadingLine /> : !groups.length ? <div className="empty-state"><span className="empty-mark"><Network size={19} /></span><div><h3>No provider connections</h3><p>Add an OpenAI compatible HTTPS endpoint and its credential using the button above. Discovered models stay private until their prices are reviewed on the Models &amp; pricing tab.</p></div></div> : <div className="provider-brand-list">{groups.map((group) => <section className="provider-brand-group" key={group.slug}><button type="button" className="provider-brand-heading" aria-expanded={openBrands.has(group.slug)} onClick={() => setOpenBrands((current) => { const next = new Set(current);

 if (next.has(group.slug)) { next.delete(group.slug); } else { next.add(group.slug); }

 return next; })}><ChevronDown size={16} aria-hidden="true" /><Network size={18} aria-hidden="true" /><span><strong>{group.name}</strong><small>{group.connections.length} connection{group.connections.length === 1 ? "" : "s"}</small></span></button>
        {openBrands.has(group.slug) && <div className="table-scroll" tabIndex={0} role="region" aria-label="Private connections"><table className="provider-connection-table"><thead><tr><th scope="col">Private connection</th><th scope="col">State</th><th scope="col">Sync / models</th><th scope="col">Provider cap</th><th scope="col">Actions</th></tr></thead><tbody>{group.connections.map((connection) => <tr key={connection.id}><td><strong>{connection.connectionLabel}</strong><small className="mono">{connection.baseUrlDisplay}</small></td><td><span className={`status-label status-${connection.health}`}>{connection.health}</span></td><td>{connection.lastSyncAt ? new Date(connection.lastSyncAt).toLocaleString("en-GB", { dateStyle: "medium", timeZone: "Europe/Berlin" }) : "Never synced"}<small>{connection.discoveredModels} discovered · {connection.approvedModels} approved</small></td><td><MoneyRunway label="Connection cap" usedUsd={connection.budget.usedUsd} limitUsd={connection.budget.limitUsd} period={connection.budget.period} reservedUsd={connection.budget.reservedUsd} remainingUsd={connection.budget.remainingUsd} resetAt={connection.budget.resetAt} /></td><td><div className="provider-actions"><button className="button button-secondary button-small" type="button" disabled={syncing === connection.id} onClick={() => { void sync(connection); }}><RefreshCw size={14} />{syncing === connection.id ? "Syncing…" : `Sync ${connection.connectionLabel}`}</button><ConnectionBudgetEditor connection={connection} portalApi={portalApi} onSaved={refresh} /></div></td></tr>)}</tbody></table></div>}
      </section>)}
    </div>}
  </>;
}
