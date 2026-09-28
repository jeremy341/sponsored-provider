import { useState } from "react";
import { ArrowDown, ArrowUp } from "lucide-react";
import type { CatalogOfferRecord, OfferRouteRecord, PortalApi } from "../../../contracts/api";

export function RoutePriorityEditor({ offer, portalApi }: { offer: CatalogOfferRecord; portalApi: PortalApi }) {
  const routes = [...offer.routes].sort((a, b) => a.order - b.order);
  const reorderable = routes.filter((route) => route.priceStatus === "matching" && !route.reviewRequired && !route.stale && route.connectionEnabled);
  const [message, setMessage] = useState("");

  async function move(routeId: string, delta: number) {
    const current = reorderable.findIndex((route) => route.id === routeId);
    const target = current + delta;

    if (current < 0 || target < 0 || target >= reorderable.length) return;
    const next = [...reorderable];
    [next[current], next[target]] = [next[target], next[current]];

    try { await portalApi.updateRouteOrder(offer.id, next.map((route) => route.connectionId)); setMessage(`${next[target].connectionLabel} moved to priority ${target + 1}.`); }
    catch { setMessage("Route priority could not be saved."); }
  }

  return <section className="operator-subsection" aria-labelledby="route-priority-title"><div className="operator-subheading"><h3 id="route-priority-title">Route priority</h3><p>Only confirmed, price-matched routes can serve requests.</p></div>
    <ol className="route-priority-list">{routes.map((route, index) => {
      const routeIndex = reorderable.findIndex((item) => item.id === route.id);
      const canReorder = routeIndex >= 0;

      return <li key={route.id} className="route-priority-row"><RouteStatus route={route} index={index} /><div className="route-move-actions"><button type="button" className="button button-quiet button-small" aria-label={`Move ${route.connectionLabel} up`} disabled={!canReorder || routeIndex === 0} onClick={() => { void move(route.id, -1); }}><ArrowUp size={15} /><span>Move up</span></button><button type="button" className="button button-quiet button-small" aria-label={`Move ${route.connectionLabel} down`} disabled={!canReorder || routeIndex === reorderable.length - 1} onClick={() => { void move(route.id, 1); }}><ArrowDown size={15} /><span>Move down</span></button></div></li>;
    })}</ol>
    <p className="sr-only" aria-live="polite">{message}</p>
  </section>;
}

function RouteStatus({ route, index }: { route: OfferRouteRecord; index: number }) {
  const mismatch = route.priceStatus === "mismatch";
  const needsMapping = route.priceStatus === "unconfirmed";
  const status = route.stale ? "Stale · excluded" : !route.connectionEnabled ? "Connection disabled" : mismatch ? "Rate mismatch · blocked" : needsMapping ? "Model mapping required" : route.reviewRequired ? "Reconfirmation required" : route.enabled ? (index === 0 ? "Primary route" : "Fallback route") : "Route disabled";

  const explanation = mismatch
    ? "Rate mismatch: this route cannot serve requests until its price matches the approved offer."
    : needsMapping
      ? "Map the discovered upstream model to this offer before enabling the route."
      : route.reviewRequired
        ? "The model is freshly discovered and prices match. Enable the route to reconfirm it."
        : null;

  return <div className="route-description"><span className="route-order">{index + 1}</span><span><strong>{route.connectionLabel}</strong><small className="mono">{route.upstreamModelId}</small><small>{status}</small>{explanation && <small className="route-warning">{explanation}</small>}</span></div>;
}
