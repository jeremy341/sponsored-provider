import { useState } from "react";
import * as Dialog from "@radix-ui/react-dialog";
import { PixelIcon } from "../../icons/PixelIcon";
import type { CatalogOfferRecord, OfferRouteRecord, PortalApi } from "../../../contracts/api";
import { PriceReviewPanel } from "./PriceReviewPanel";
import { RoutePriorityEditor } from "./RoutePriorityEditor";

export function OfferDetailSheet({ offer, offers, portalApi, onChanged, onClose }: { offer: CatalogOfferRecord | null; offers: CatalogOfferRecord[]; portalApi: PortalApi; onChanged: () => void; onClose: () => void }) {
  const [error, setError] = useState("");
  const [mappingTargets, setMappingTargets] = useState<Record<string, string>>({});
  const [mappingNotice, setMappingNotice] = useState("");

  async function setAvailable(available: boolean) {
    if (!offer) return;

    setError("");

    try { await portalApi.setOfferAvailable(offer.id, available); onChanged(); }
    catch { setError("Could not update model availability. Existing settings are unchanged."); }
  }

  async function mapRoute(route: OfferRouteRecord) {
    if (!offer) return;
    const targetOfferId = mappingTargets[route.id] ?? offer.id;
    setError("");
    setMappingNotice("");

    try {
      await portalApi.mapConnectionModel(route.connectionId, route.upstreamModelId, targetOfferId);
      setMappingNotice(`${route.upstreamModelId} mapped to ${offers.find((item) => item.id === targetOfferId)?.canonicalModelId ?? "the selected offer"}.`);
      onChanged();
    } catch {
      setError("Model mapping could not be saved. Choose an offer from the same provider brand and verify the upstream model.");
    }
  }

  return <Dialog.Root open={Boolean(offer)} onOpenChange={(open) => { if (!open) onClose(); }}>
    <Dialog.Portal><Dialog.Overlay className="dialog-overlay" /><Dialog.Content className="dialog-content offer-sheet" aria-describedby="offer-description">
      {offer && <><div className="dialog-title-row"><div><Dialog.Title>{offer.displayName}</Dialog.Title><Dialog.Description id="offer-description">{offer.brandName} · public model ID <code>{offer.canonicalModelId}</code></Dialog.Description></div><Dialog.Close asChild><button className="icon-button" aria-label="Close offer details"><PixelIcon name="close" /></button></Dialog.Close></div>
        <label className="offer-availability"><span><strong>Available to developers</strong><small>{offer.activePrice ? "Offer-level access; route switches are managed separately." : "Price required before publication."}</small></span><input type="checkbox" role="switch" aria-label="Available to developers" checked={offer.available} disabled={!offer.activePrice || !offer.approved} onChange={(event) => { void setAvailable(event.target.checked); }} /></label>
        {!offer.activePrice && <p className="inline-notice notice-warning" role="status">Price required. This offer is unavailable to users.</p>}
        {error && <p className="inline-notice notice-error" role="alert">{error}</p>}
        <PriceReviewPanel offer={offer} portalApi={portalApi} onChanged={onChanged} />
        <section className="operator-subsection"><div className="operator-subheading"><h3>Connections and routes</h3><p>Private connection names remain separate from the public model ID.</p></div><RoutePriorityEditor offer={offer} portalApi={portalApi} />
          {offer.routes.map((route) => <div className="route-control" key={route.id}><label className="route-toggle"><span><strong>{route.connectionLabel}</strong><small>{route.reviewRequired ? "Reconfirmation required" : route.active ? "Currently selected" : "Route availability"}</small></span><input type="checkbox" role="switch" aria-label={`Enable route ${route.connectionLabel}`} checked={route.enabled} disabled={route.stale || !route.connectionEnabled || route.priceStatus !== "matching"} onChange={async (event) => {
            setError("");

            try { await portalApi.setRouteAvailability(route.id, event.target.checked); onChanged(); }
            catch { setError("Could not update route availability. Confirm its model mapping, fresh discovery, and matching price."); }
          }} /></label>
            {route.priceStatus === "unconfirmed" && <div className="route-mapping-control"><label><span className="field-label">Canonical model for {route.connectionLabel}</span><select aria-label={`Canonical model for ${route.connectionLabel}`} value={mappingTargets[route.id] ?? offer.id} onChange={(event) => setMappingTargets((current) => ({ ...current, [route.id]: event.target.value }))}>{offers.filter((item) => item.brandSlug === offer.brandSlug).map((item) => <option key={item.id} value={item.id}>{item.displayName} · {item.canonicalModelId}</option>)}</select></label><button type="button" className="button button-secondary button-small" onClick={() => { void mapRoute(route); }}>Map {route.connectionLabel}</button></div>}
          </div>)}
          {mappingNotice && <p className="field-help" role="status">{mappingNotice}</p>}
        </section></>}
    </Dialog.Content></Dialog.Portal>
  </Dialog.Root>;
}
