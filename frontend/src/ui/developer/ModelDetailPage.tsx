import { useEffect, useState } from "react";
import { Link, useLocation, useParams } from "react-router-dom";
import { ArrowLeft, Check, Copy } from "lucide-react";
import type { ModelRecord, PortalApi } from "../../contracts/api";
import { formatUsd } from "../../lib/money";
import { getLayoutPreviewRole } from "../../lib/preview";
import { ModelCodeExamples } from "./ModelCodeExamples";

export function ModelDetailPage({ portalApi }: { portalApi: Pick<PortalApi, "listModels"> }) {
  const { "*": routeId = "" } = useParams();
  const location = useLocation();
  const [models, setModels] = useState<ModelRecord[] | null>(null);
  const [loadError, setLoadError] = useState(false);
  const [copied, setCopied] = useState(false);

  useEffect(() => {
    let active = true;

    if (getLayoutPreviewRole() === "developer") {
      setModels([]);

      return () => { active = false; };
    }

    setModels(null);
    setLoadError(false);
    portalApi.listModels().then((result) => {
      if (active) setModels(result);
    }).catch(() => {
      if (active) setLoadError(true);
    });

    return () => { active = false; };
  }, [portalApi]);

  const model = models?.find((entry) => entry.id === routeId) ?? null;
  const returnTo = `/developer/models${location.search}`;

  async function copyId(id: string) {
    try {
      await navigator.clipboard.writeText(id);
      setCopied(true);
      window.setTimeout(() => setCopied(false), 1600);
    } catch {
      setCopied(false);
    }
  }

  if (models === null && !loadError) return <section className="section-block" aria-label="Model details"><div className="loading-line" role="status"><span className="sr-only">Loading model details</span></div></section>;

  if (loadError) return <section className="section-block model-unavailable" aria-label="Model unavailable"><Link className="text-link model-back-link" to={returnTo}><ArrowLeft size={15} /> Back to models</Link><h1>Model details unavailable</h1><p>The published catalog could not be loaded. Try again from the model list.</p></section>;

  if (!model) return <section className="section-block model-unavailable" aria-label="Model unavailable"><Link className="text-link model-back-link" to={returnTo}><ArrowLeft size={15} /> Back to models</Link><span className="eyebrow">Catalog entry not found</span><h1>Model unavailable</h1><p>This model is no longer in the published catalog. Historical activity remains in your usage history, but this ID cannot be used for new requests.</p></section>;

  const displayName = model.displayName ?? model.id.split("::").at(-1) ?? model.id;

  return <article className="model-detail-page">
    <Link className="text-link model-back-link" to={returnTo}><ArrowLeft size={15} /> Back to models</Link>
    <header className="model-detail-header"><div><span className="eyebrow">{model.providerName} · {model.capabilities.map((item) => item === "vision" ? "Vision" : "Text").join(" + ")}</span><h1>{displayName}</h1><p>{model.available ? "Available for new requests" : "Currently unavailable"} · OpenAI-compatible chat</p></div><button type="button" className="button button-secondary model-id-copy" onClick={() => { void copyId(model.id); }}>{copied ? <Check size={15} aria-hidden="true" /> : <Copy size={15} aria-hidden="true" />}{copied ? "Copied" : "Copy model ID"}</button></header>
    <span className="sr-only" aria-live="polite">{copied ? "Model ID copied to clipboard" : ""}</span>
    <div className="model-public-id"><span>API model ID</span><code>{model.id}</code></div>
    <section className="model-detail-prices" aria-label="Model pricing">
      <PriceCard label="Input" value={model.pricingVerified ? model.inputUsdPerMillion : null} verified={model.pricingVerified} />
      <PriceCard label="Output" value={model.pricingVerified ? model.outputUsdPerMillion : null} verified={model.pricingVerified} />
      <PriceCard label="Cached input" value={model.pricingVerified ? model.cacheUsdPerMillion : null} verified={model.pricingVerified} />
    </section>
    <p className="model-price-provenance">{model.pricingVerified ? `Verified pricing · ${model.priceSource ?? "source not reported"}` : "Pricing is not verified; rates are unavailable."}{model.syncedAt ? ` · Catalog synced ${new Intl.DateTimeFormat("en-GB", { dateStyle: "medium", timeZone: "Europe/Berlin" }).format(new Date(model.syncedAt))}` : ""}</p>
    <section className="model-technical-details" aria-labelledby="technical-details-heading"><h2 id="technical-details-heading">Technical details</h2><dl><div><dt>Provider</dt><dd>{model.providerName}</dd></div><div><dt>Capabilities</dt><dd>{model.capabilities.length ? model.capabilities.join(", ") : "Not reported"}</dd></div><div><dt>Availability</dt><dd>{model.available ? "Available" : "Unavailable"}</dd></div><div><dt>Active routes</dt><dd>{model.activeRouteCount == null ? "Not reported" : model.activeRouteCount}</dd></div></dl></section>
    {model.available ? <ModelCodeExamples modelId={model.id} /> : <p className="model-example-safety">This offer is unavailable, so new requests will not be accepted.</p>}
  </article>;
}

function PriceCard({ label, value, verified }: { label: string; value: string | null; verified: boolean }) {
  const reported = verified && value != null;

  return <div className="model-detail-price"><span>{label} price</span><strong>{reported ? formatUsd(value) : "Not reported"}</strong><small>{reported ? "USD per 1M tokens" : verified ? "No rate supplied" : "Pricing not verified"}</small></div>;
}
