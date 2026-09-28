import { useState } from "react";
import { PixelIcon } from "../../icons/PixelIcon";
import type { CatalogOfferRecord, PortalApi } from "../../../contracts/api";
import { formatUsd } from "../../../lib/money";

export function PriceReviewPanel({ offer, portalApi, onChanged }: { offer: CatalogOfferRecord; portalApi: PortalApi; onChanged: () => void }) {
  const [input, setInput] = useState(offer.pendingPrice?.inputUsdPerMillion ?? "");
  const [output, setOutput] = useState(offer.pendingPrice?.outputUsdPerMillion ?? "");
  const [cachedInput, setCachedInput] = useState(offer.pendingPrice?.cachedInputUsdPerMillion ?? "");
  const [source, setSource] = useState(offer.pendingPrice?.source ?? "");
  const [message, setMessage] = useState("");
  const [busy, setBusy] = useState(false);

  async function save(approve: boolean) {
    const validRate = (value: string) => /^(?:0|[1-9]\d*)(?:\.\d+)?$/.test(value);

    if (!validRate(input) || !validRate(output) || (cachedInput && !validRate(cachedInput)) || !source.trim()) { setMessage("Enter nonnegative decimal rates and a price source.");

 return; }

    setBusy(true); setMessage("");

    try {
      const pending = await portalApi.updateOfferPrice(offer.id, { inputUsdPerMillion: input, outputUsdPerMillion: output, cachedInputUsdPerMillion: cachedInput || null, source: source.trim() });

      if (approve) await portalApi.approveOfferPrice(offer.id, pending.id);
      setMessage(approve ? "Price saved and approved." : "Price suggestion saved for review."); onChanged();
    } catch { setMessage("The price update could not be saved. Check the rates and try again."); }
    finally { setBusy(false); }
  }

  return <section className="operator-subsection" aria-labelledby="price-review-title"><div className="operator-subheading"><h3 id="price-review-title">Price review</h3><p>USD per 1M tokens. Approval and user availability are separate controls.</p></div>
    <div className="price-comparison"><div><span>Active price</span>{offer.activePrice ? <strong>{formatUsd(offer.activePrice.inputUsdPerMillion)} input · {formatUsd(offer.activePrice.outputUsdPerMillion)} output</strong> : <strong>Price required</strong>}{offer.activePrice?.cachedInputUsdPerMillion != null && <small>{formatUsd(offer.activePrice.cachedInputUsdPerMillion)} cached input</small>}<small>{offer.activePrice?.source ?? "No approved source"}</small></div><div><span>Pending price</span>{offer.pendingPrice ? <strong>{formatUsd(offer.pendingPrice.inputUsdPerMillion)} input · {formatUsd(offer.pendingPrice.outputUsdPerMillion)} output</strong> : <strong>No pending change</strong>}{offer.pendingPrice?.cachedInputUsdPerMillion != null && <small>{formatUsd(offer.pendingPrice.cachedInputUsdPerMillion)} cached input</small>}<small>{offer.pendingPrice?.source ?? "Enter a verified source below"}</small></div></div>
    {!offer.activePrice && <p className="inline-notice notice-warning"><PixelIcon name="money" /> Price required. This offer stays unavailable to developers until approved rates are recorded.</p>}
    <div className="form-two-col model-price-fields"><label><span className="field-label">Input USD / 1M</span><input aria-label="Input USD per 1M tokens" inputMode="decimal" value={input} onChange={(event) => setInput(event.target.value)} /></label><label><span className="field-label">Output USD / 1M</span><input aria-label="Output USD per 1M tokens" inputMode="decimal" value={output} onChange={(event) => setOutput(event.target.value)} /></label><label><span className="field-label">Cached input USD / 1M (optional)</span><input aria-label="Cached input USD per 1M tokens" inputMode="decimal" value={cachedInput} onChange={(event) => setCachedInput(event.target.value)} /></label><label className="price-source-field"><span className="field-label">Price source</span><input aria-label="Price source" value={source} onChange={(event) => setSource(event.target.value)} placeholder="Verified source" /></label></div>
    <div className="model-policy-actions"><button type="button" className="button button-secondary" disabled={busy} onClick={() => { void save(false); }}>Save suggestion</button><button type="button" className="button button-primary" disabled={busy || !offer.pendingPrice && !source.trim()} onClick={() => { void save(true); }}><PixelIcon name="confirm" /> Approve price</button>{message && <span role="status" className="field-help">{message}</span>}</div>
  </section>;
}
