import { useEffect, useMemo, useState } from "react";
import { Boxes, ChevronDown } from "lucide-react";
import type { CatalogOfferRecord, PortalApi, ProviderConnectionRecord } from "../../../contracts/api";
import { formatUsd } from "../../../lib/money";
import { getLayoutPreviewRole } from "../../../lib/preview";
import { DataNotice, LoadingLine, PageHeader } from "../../shared";
import { OfferDetailSheet } from "../providers/OfferDetailSheet";

/** Model catalog and price approval, split out of the former combined
 *  "Providers & models" page so each concern gets its own tab. */
export function ModelsPricingPage({ portalApi }: { portalApi: PortalApi }) {
  const [providers, setProviders] = useState<ProviderConnectionRecord[]>([]);
  const [offers, setOffers] = useState<CatalogOfferRecord[]>([]);
  const [selected, setSelected] = useState<CatalogOfferRecord | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [openBrands, setOpenBrands] = useState<Set<string>>(new Set());

  const refresh = () => {
    if (getLayoutPreviewRole() === "operator") {
      setProviders([]);
      setOffers([]);
      setSelected(null);
      setError(null);
      setLoading(false);

      return;
    }

    setLoading(true); setError(null);
    Promise.all([portalApi.listProviders(), portalApi.listOperatorOffers()]).then(([connections, catalog]) => { setProviders(connections); setOffers(catalog); setSelected((current) => current ? catalog.find((item) => item.id === current.id) ?? null : null); setOpenBrands(new Set(catalog.map((item) => item.brandSlug ?? `unmapped:${item.id}`))); })
      .catch(() => setError("The model catalog could not be loaded. Retry to refresh the current prices."))
      .finally(() => setLoading(false));
  };

  useEffect(refresh, [portalApi]);

  const groups = useMemo(() => {
    const map = new Map<string, { slug: string; name: string; offers: CatalogOfferRecord[] }>();
    offers.forEach((offer) => {
      const slug = offer.brandSlug ?? `unmapped:${offer.id}`;
      const group = map.get(slug) ?? { slug, name: offer.brandName, offers: [] };
      group.offers.push(offer);
      map.set(slug, group);
    });

    return [...map.values()];
  }, [offers]);

  const connectionsByBrand = useMemo(() => {
    const map = new Map<string, ProviderConnectionRecord[]>();
    providers.forEach((connection) => {
      if (!connection.brandSlug) return;
      map.set(connection.brandSlug, [...(map.get(connection.brandSlug) ?? []), connection]);
    });

    return map;
  }, [providers]);

  return <>
    <PageHeader title="Models &amp; pricing" description="Review discovered offers, approve prices, and control publication." />
    <DataNotice error={error} onRetry={refresh} />
    {loading ? <LoadingLine /> : !groups.length ? <div className="empty-state"><span className="empty-mark"><Boxes size={19} /></span><div><h3>No catalog offers yet</h3><p>Offers appear here after a provider connection is added and its models are discovered on the Providers tab.</p></div></div> : <div className="provider-brand-list">{groups.map((group) => {
      const brandConnections = connectionsByBrand.get(group.slug) ?? [];

      return <section className="provider-brand-group" key={group.slug}><button type="button" className="provider-brand-heading" aria-expanded={openBrands.has(group.slug)} onClick={() => setOpenBrands((current) => { const next = new Set(current);

 if (next.has(group.slug)) { next.delete(group.slug); } else { next.add(group.slug); }

 return next; })}><ChevronDown size={16} aria-hidden="true" /><Boxes size={18} aria-hidden="true" /><span><strong>{group.name}</strong><small>{group.offers.length} catalog offer{group.offers.length === 1 ? "" : "s"} · {brandConnections.length} connection{brandConnections.length === 1 ? "" : "s"}</small></span></button>
        {openBrands.has(group.slug) && <div className="offer-catalog"><div className="operator-subheading"><h2>Catalog offers</h2><p>Price approval controls whether an offer can be published.</p></div><div className="table-scroll" tabIndex={0} role="region" aria-label="Catalog offers"><table><thead><tr><th scope="col">Model</th><th scope="col">Price</th><th scope="col">Availability</th><th scope="col">Routes</th></tr></thead><tbody>{group.offers.map((offer) => <tr key={offer.id}><td><button className="text-link offer-open" type="button" onClick={() => setSelected(offer)}><strong>{offer.displayName}</strong></button><small className="mono">{offer.canonicalModelId}</small></td><td>{offer.activePrice ? <>{formatUsd(offer.activePrice.inputUsdPerMillion)} input · {formatUsd(offer.activePrice.outputUsdPerMillion)} output<small>{offer.activePrice.source ?? "Source not reported"}</small></> : <span className="status-label status-pending">Price required</span>}</td><td>{!offer.approved ? "Pending approval" : offer.available ? "Published" : "Off"}</td><td>{offer.routes.filter((route) => route.enabled && !route.stale && !route.reviewRequired).length} eligible / {offer.routes.length} total</td></tr>)}</tbody></table></div></div>}
      </section>;
    })}</div>}
    <OfferDetailSheet offer={selected} offers={offers} portalApi={portalApi} onChanged={refresh} onClose={() => setSelected(null)} />
  </>;
}
