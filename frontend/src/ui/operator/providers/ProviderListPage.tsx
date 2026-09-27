import { useEffect, useMemo, useState } from "react";
import { ChevronDown, Network, RefreshCw } from "lucide-react";
import type { CatalogOfferRecord, PortalApi, ProviderConnectionRecord } from "../../../contracts/api";
import { formatUsd } from "../../../lib/money";
import { MoneyRunway } from "../MoneyRunway";
import { ConnectionBudgetEditor } from "./ConnectionBudgetEditor";
import { ConnectionDialog } from "./ConnectionDialog";
import { OfferDetailSheet } from "./OfferDetailSheet";

export function ProviderListPage({ portalApi }: { portalApi: PortalApi }) {
  const [providers, setProviders] = useState<ProviderConnectionRecord[]>([]);
  const [offers, setOffers] = useState<CatalogOfferRecord[]>([]);
  const [selected, setSelected] = useState<CatalogOfferRecord | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState("");
  const [syncing, setSyncing] = useState<string | null>(null);
  const [openBrands, setOpenBrands] = useState<Set<string>>(new Set());

  const refresh = () => {
    setLoading(true); setError(null);
    Promise.all([portalApi.listProviders(), portalApi.listOperatorOffers()]).then(([connections, catalog]) => { setProviders(connections); setOffers(catalog); setSelected((current) => current ? catalog.find((item) => item.id === current.id) ?? null : null); setOpenBrands(new Set(connections.map((item) => item.brandSlug))); })
      .catch(() => setError("Provider data could not be loaded. Retry to refresh the current catalog."))
      .finally(() => setLoading(false));
  };

  useEffect(refresh, [portalApi]);

  const groups = useMemo(() => {
    const map = new Map<string, { name: string; connections: ProviderConnectionRecord[] }>();
    providers.forEach((connection) => { const group = map.get(connection.brandSlug) ?? { name: connection.brandName, connections: [] }; group.connections.push(connection); map.set(connection.brandSlug, group); });

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

  const offersByBrand = (slug: string) => offers.filter((offer) => offer.brandSlug === slug);

  return <>
    <header className="page-header"><div><h1>Providers &amp; models</h1><p>Manage upstream connections, published offers, prices, and route priority.</p></div><div className="page-header-action"><ConnectionDialog portalApi={portalApi} onCreated={(summary) => { setNotice(summary); refresh(); }} /></div></header>
    {notice && <div className={`inline-notice ${notice.toLowerCase().includes("failed") ? "notice-error" : "notice-info"}`} role={notice.toLowerCase().includes("failed") ? "alert" : "status"}><Network size={16} /><span>{notice}</span></div>}
    {error && <div className="inline-notice notice-error" role="alert"><span>{error}</span><button className="button button-small" type="button" onClick={refresh}>Retry</button></div>}
    {loading ? <div className="loading-line" role="status"><span className="sr-only">Loading providers</span></div> : !groups.length ? <div className="empty-state"><span className="empty-mark"><Network size={19} /></span><div><h3>No provider connections</h3><p>Add an OpenAI compatible HTTPS endpoint and its credential. Discovered models remain private until their mapping and prices are reviewed.</p><div className="empty-action"><ConnectionDialog portalApi={portalApi} onCreated={(summary) => { setNotice(summary); refresh(); }} /></div></div></div> : <div className="provider-brand-list">{groups.map((group) => {
      const brandOffers = offersByBrand(group.slug);

      return <section className="provider-brand-group" key={group.slug}><button type="button" className="provider-brand-heading" aria-expanded={openBrands.has(group.slug)} onClick={() => setOpenBrands((current) => { const next = new Set(current);

 if (next.has(group.slug)) { next.delete(group.slug); } else { next.add(group.slug); }

 return next; })}><ChevronDown size={16} aria-hidden="true" /><Network size={18} aria-hidden="true" /><span><strong>{group.name}</strong><small>{group.connections.length} connection{group.connections.length === 1 ? "" : "s"} · {brandOffers.length} catalog offers</small></span></button>
        {openBrands.has(group.slug) && <><div className="table-scroll"><table className="provider-connection-table"><thead><tr><th>Private connection</th><th>State</th><th>Sync / models</th><th>Provider cap</th><th>Actions</th></tr></thead><tbody>{group.connections.map((connection) => <tr key={connection.id}><td><strong>{connection.connectionLabel}</strong><small className="mono">{connection.baseUrlDisplay}</small></td><td><span className={`status-label status-${connection.health}`}>{connection.health}</span></td><td>{connection.lastSyncAt ? new Date(connection.lastSyncAt).toLocaleString("en-GB", { dateStyle: "medium", timeZone: "Europe/Berlin" }) : "Never synced"}<small>{connection.discoveredModels} discovered · {connection.approvedModels} approved</small></td><td><MoneyRunway label="Connection cap" usedUsd={connection.budget.usedUsd} limitUsd={connection.budget.limitUsd} period={connection.budget.period} reservedUsd={connection.budget.reservedUsd} remainingUsd={connection.budget.remainingUsd} resetAt={connection.budget.resetAt} /></td><td><div className="provider-actions"><button className="button button-secondary button-small" type="button" disabled={syncing === connection.id} onClick={() => { void sync(connection); }}><RefreshCw size={14} />{syncing === connection.id ? "Syncing…" : `Sync ${connection.connectionLabel}`}</button><ConnectionBudgetEditor connection={connection} portalApi={portalApi} onSaved={refresh} /></div></td></tr>)}</tbody></table></div>
          <div className="offer-catalog"><div className="operator-subheading"><h2>Catalog offers</h2><p>Price approval controls whether an offer can be published.</p></div>{brandOffers.length ? <div className="table-scroll"><table><thead><tr><th>Model</th><th>Price</th><th>Availability</th><th>Routes</th></tr></thead><tbody>{brandOffers.map((offer) => <tr key={offer.id}><td><button className="text-link offer-open" type="button" onClick={() => setSelected(offer)}><strong>{offer.displayName}</strong></button><small className="mono">{offer.canonicalModelId}</small></td><td>{offer.activePrice ? <>{formatUsd(offer.activePrice.inputUsdPerMillion)} input · {formatUsd(offer.activePrice.outputUsdPerMillion)} output<small>{offer.activePrice.source ?? "Source not reported"}</small></> : <span className="status-label status-pending">Price required</span>}</td><td>{!offer.approved ? "Pending approval" : offer.available ? "Published" : "Off"}</td><td>{offer.routes.filter((route) => route.enabled && !route.stale && !route.reviewRequired).length} eligible / {offer.routes.length} total</td></tr>)}</tbody></table></div> : <p className="field-help">No catalog offers have been discovered for this brand.</p>}</div>
        </>}
      </section>;
    })}</div>}
    <OfferDetailSheet offer={selected} offers={offers} portalApi={portalApi} onChanged={refresh} onClose={() => setSelected(null)} />
  </>;
}
