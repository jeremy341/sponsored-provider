import { useEffect, useMemo, useState } from "react";
import * as Dialog from "@radix-ui/react-dialog";
import { Copy, Search, X } from "lucide-react";
import type { ModelRecord, PortalApi } from "../../contracts/api";
import { formatUsd } from "../../lib/money";

export function ModelCatalogPage({ portalApi }: { portalApi: PortalApi }) {
  const [models, setModels] = useState<ModelRecord[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [search, setSearch] = useState("");
  const [provider, setProvider] = useState("all");
  const [capability, setCapability] = useState("all");
  const [priceSort, setPriceSort] = useState("provider");
  const [selected, setSelected] = useState<ModelRecord | null>(null);

  async function load() {
    setLoading(true);
    setError("");

    try { setModels(await portalApi.listModels()); }
    catch { setError("The published model catalog could not be loaded. Retry or contact the operator."); }
    finally { setLoading(false); }
  }

  useEffect(() => { void load(); }, [portalApi]);

  const providers = useMemo(() => [...new Set(models.map((model) => model.providerName))].sort((left, right) => left.localeCompare(right)), [models]);

  const filtered = useMemo(() => {
    const query = search.trim().toLowerCase();

    const matching = models.filter((model) => {
      const matchesCapability = capability === "all" || model.capabilities.some((item) => item === capability);

      return `${model.providerName} ${model.displayName ?? model.id} ${model.id}`.toLowerCase().includes(query)
        && (provider === "all" || model.providerName === provider)
        && matchesCapability;
    });

    if (priceSort !== "input_asc" && priceSort !== "input_desc") return matching;

    return [...matching].sort((left, right) => {
      const comparison = compareDecimal(left.inputUsdPerMillion, right.inputUsdPerMillion);

      return priceSort === "input_asc" ? comparison : -comparison;
    });
  }, [models, search, provider, capability, priceSort]);

  const grouped = useMemo(() => {
    const result = new Map<string, ModelRecord[]>();

    for (const model of filtered) result.set(model.providerName, [...(result.get(model.providerName) ?? []), model]);

    return [...result.entries()];
  }, [filtered]);

  return <>
    <header className="page-header"><div><h1>Models</h1><p>Browse published models and their verified USD rates. API IDs stay provider-scoped.</p></div></header>
    {error && <div className="inline-notice notice-error" role="alert">{error} <button type="button" className="button button-small" onClick={() => { void load(); }}>Retry</button></div>}
    <section className="section-block table-section"><div className="toolbar model-catalog-toolbar">
      <label className="search-field"><Search size={16} aria-hidden="true" /><span className="sr-only">Search models</span><input value={search} onChange={(event) => setSearch(event.target.value)} placeholder="Search providers or models" /></label>
      <label className="select-filter"><span className="sr-only">Filter by provider</span><select aria-label="Filter by provider" value={provider} onChange={(event) => setProvider(event.target.value)}><option value="all">All providers</option>{providers.map((name) => <option key={name} value={name}>{name}</option>)}</select></label>
      <label className="select-filter"><span className="sr-only">Filter by capability</span><select aria-label="Filter by capability" value={capability} onChange={(event) => setCapability(event.target.value)}><option value="all">All capabilities</option><option value="text">Text</option><option value="vision">Vision</option></select></label>
      <label className="select-filter"><span className="sr-only">Sort by input price</span><select aria-label="Sort by input price" value={priceSort} onChange={(event) => setPriceSort(event.target.value)}><option value="provider">Provider order</option><option value="input_asc">Lowest input price</option><option value="input_desc">Highest input price</option></select></label>
      <span className="count-label">{loading ? "Loading…" : `${filtered.length} models`}</span>
    </div>
    {loading ? <div className="loading-line" role="status"><span className="sr-only">Loading models</span></div> : grouped.length ? <div className="developer-model-groups">{grouped.map(([name, entries]) => <section className="developer-model-group" key={name}><h2>{name}</h2><div className="developer-model-grid">{entries.map((model) => <article className="developer-model-row" key={model.id}><div className="developer-model-identity"><strong>{model.displayName ?? model.id.split("::").at(-1)}</strong><span className="mono">{model.id}</span><div className="model-capability-list">{model.capabilities.map((item) => <span className="model-capability" key={item}>{item}</span>)}</div></div><div className="developer-model-rates"><span>{formatUsd(model.inputUsdPerMillion)} / 1M input</span><span>{formatUsd(model.outputUsdPerMillion)} / 1M output</span></div><button type="button" className="button button-secondary button-small" aria-label={`View details for ${model.providerName} / ${model.displayName ?? model.id.split("::").at(-1)}`} onClick={() => setSelected(model)}>Details</button></article>)}</div></section>)}</div> : <div className="empty-state"><div><h3>{models.length ? "No models match" : "No published models yet"}</h3><p>{models.length ? "Change the filters to see more of your provider catalog." : "Models appear here after the operator verifies their price and publishes them."}</p></div></div>}
    </section>
    <ModelDetailDialog model={selected} onClose={() => setSelected(null)} />
  </>;
}

function ModelDetailDialog({ model, onClose }: { model: ModelRecord | null; onClose: () => void }) {
  const [copied, setCopied] = useState(false);
  const endpoint = `${window.location.origin}/v1`;

  const snippet = model ? [
    `curl ${endpoint}/chat/completions \\`,
    '  -H "Authorization: Bearer YOUR_API_KEY" \\',
    '  -H "Content-Type: application/json" \\',
    `  -d '{"model":"${model.id}","messages":[{"role":"user","content":"Hello"}]}'`,
  ].join("\n") : "";


  async function copyModelId() {
    if (!model) return;

    try { await navigator.clipboard.writeText(model.id); setCopied(true); }
    catch { setCopied(false); }
  }

  return <Dialog.Root open={Boolean(model)} onOpenChange={(open) => { if (!open) onClose(); }}><Dialog.Portal><Dialog.Overlay className="dialog-overlay" /><Dialog.Content className="dialog-content model-detail-dialog" aria-describedby="model-detail-description">
    {model && <><div className="dialog-title-row"><div><Dialog.Title>{model.displayName ?? model.id.split("::").at(-1)}</Dialog.Title><Dialog.Description id="model-detail-description">{model.providerName} · OpenAI-compatible chat model</Dialog.Description></div><Dialog.Close asChild><button type="button" className="icon-button" aria-label="Close model details"><X size={18} /></button></Dialog.Close></div>
      <div className="model-public-id"><span>API model ID</span><code>{model.id}</code><button type="button" className="button button-quiet button-small" onClick={() => { void copyModelId(); }}><Copy size={14} />{copied ? "Copied" : "Copy ID"}</button></div>
      <div className="model-price-strip"><div><span>Input</span><strong>{formatUsd(model.inputUsdPerMillion)}</strong><small>USD / 1M tokens</small></div><div><span>Output</span><strong>{formatUsd(model.outputUsdPerMillion)}</strong><small>USD / 1M tokens</small></div>{model.pricingVerified && model.cacheUsdPerMillion != null && <div><span>Cached input</span><strong>{formatUsd(model.cacheUsdPerMillion)}</strong><small>USD / 1M tokens</small></div>}</div>
      <p className="model-price-provenance">{model.pricingVerified ? `Price source: ${model.priceSource ?? "verified source not named"}` : "Price source has not been verified."}{model.syncedAt ? ` · Catalog synced ${new Intl.DateTimeFormat("en-GB", { dateStyle: "medium", timeZone: "Europe/Berlin" }).format(new Date(model.syncedAt))}` : ""}</p>
      <section className="operator-subsection"><div className="operator-subheading"><h3>OpenAI-compatible example</h3><p>Use your own sponsored API key. Never place it in a public repository.</p></div><pre className="code-block model-example"><code>{snippet}</code></pre></section>
    </>}
  </Dialog.Content></Dialog.Portal></Dialog.Root>;
}

function compareDecimal(left: string | null, right: string | null): number {
  if (left == null) return right == null ? 0 : 1;

  if (right == null) return -1;

  const parts = [left, right].map((value) => value.split("."));
  const scale = Math.max(parts[0][1]?.length ?? 0, parts[1][1]?.length ?? 0);
  const values = parts.map(([whole, fraction = ""]) => BigInt(whole) * 10n ** BigInt(scale) + BigInt(fraction.padEnd(scale, "0") || "0"));

  return values[0] < values[1] ? -1 : values[0] > values[1] ? 1 : 0;
}
