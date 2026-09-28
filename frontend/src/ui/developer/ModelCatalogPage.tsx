import { useEffect, useMemo, useState } from "react";
import { Link, useLocation, useSearchParams } from "react-router-dom";
import { Check, Copy, Search } from "lucide-react";
import type { ModelRecord, PortalApi } from "../../contracts/api";
import { formatUsd } from "../../lib/money";
import { getLayoutPreviewRole } from "../../lib/preview";

const INITIAL_GROUP_SIZE = 6;

export function ModelCatalogPage({ portalApi }: { portalApi: Pick<PortalApi, "listModels"> }) {
  const [models, setModels] = useState<ModelRecord[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [searchParams] = useSearchParams();
  const location = useLocation();
  const [search, setSearch] = useState(searchParams.get("search") ?? "");
  const [provider, setProvider] = useState(searchParams.get("provider") ?? "all");
  const [capability, setCapability] = useState(searchParams.get("capability") ?? "all");
  const [priceSort, setPriceSort] = useState(searchParams.get("sort") ?? "provider");
  const [expandedProviders, setExpandedProviders] = useState<string[]>([]);
  const [copiedId, setCopiedId] = useState<string | null>(null);

  async function load() {
    if (getLayoutPreviewRole() === "developer") {
      setModels([]);
      setLoading(false);
      setError("");

      return;
    }

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

  function filtersQuery() {
    const params = new URLSearchParams();

    if (search.trim()) params.set("search", search.trim());

    if (provider !== "all") params.set("provider", provider);

    if (capability !== "all") params.set("capability", capability);

    if (priceSort !== "provider") params.set("sort", priceSort);

    return params.size ? `?${params.toString()}` : "";
  }

  async function copyId(modelId: string) {
    try {
      await navigator.clipboard.writeText(modelId);
      setCopiedId(modelId);
      window.setTimeout(() => setCopiedId((current) => current === modelId ? null : current), 1600);
    } catch {
      setCopiedId(null);
    }
  }

  function toggleProvider(name: string) {
    setExpandedProviders((current) => current.includes(name) ? current.filter((item) => item !== name) : [...current, name]);
  }

  return <>
    <header className="page-header"><div><h1>Models</h1><p>Compare published models by provider, capability, and verified USD rates.</p></div></header>
    {error && <div className="inline-notice notice-error" role="alert">{error} <button type="button" className="button button-small" onClick={() => { void load(); }}>Retry</button></div>}
    <section className="section-block table-section" aria-label="Published model catalog">
      <div className="toolbar model-catalog-toolbar">
        <label className="search-field"><Search size={16} aria-hidden="true" /><span className="sr-only">Search models</span><input value={search} onChange={(event) => setSearch(event.target.value)} placeholder="Search providers or models" /></label>
        <label className="select-filter"><span className="sr-only">Filter by provider</span><select aria-label="Filter by provider" value={provider} onChange={(event) => setProvider(event.target.value)}><option value="all">All providers</option>{providers.map((name) => <option key={name} value={name}>{name}</option>)}</select></label>
        <label className="select-filter"><span className="sr-only">Filter by capability</span><select aria-label="Filter by capability" value={capability} onChange={(event) => setCapability(event.target.value)}><option value="all">All capabilities</option><option value="text">Text</option><option value="vision">Vision</option></select></label>
        <label className="select-filter"><span className="sr-only">Sort by input price</span><select aria-label="Sort by input price" value={priceSort} onChange={(event) => setPriceSort(event.target.value)}><option value="provider">Provider order</option><option value="input_asc">Lowest input price</option><option value="input_desc">Highest input price</option></select></label>
        <span className="count-label" aria-live="polite">{loading ? "Loading…" : `${filtered.length} models`}</span>
      </div>
      <span className="sr-only" aria-live="polite">{copiedId ? "Model ID copied to clipboard" : ""}</span>
      {loading ? <div className="loading-line" role="status"><span className="sr-only">Loading models</span></div> : grouped.length ? <div className="developer-model-groups">{grouped.map(([name, entries]) => {
        const expanded = expandedProviders.includes(name);
        const visible = expanded ? entries : entries.slice(0, INITIAL_GROUP_SIZE);

        return <section className="developer-model-group" key={name} aria-label={`${name} models`}>
          <div className="developer-model-group-heading"><h2>{name}</h2><span>{entries.length} {entries.length === 1 ? "model" : "models"}</span></div>
          <div className="developer-model-grid">{visible.map((model) => {
            const displayName = model.displayName ?? model.id.split("::").at(-1) ?? model.id;
            const destination = `/developer/models/${encodeURIComponent(model.id)}${filtersQuery()}`;

            return <article className="developer-model-card" key={model.id} aria-label={displayName}>
              <div className="developer-model-card-top"><span className="provider-kicker">{model.providerName}</span><span className={`model-state${model.available ? " is-available" : ""}`}>{model.available ? "Available" : "Unavailable"}</span></div>
              <h3><Link to={destination} state={{ from: `${location.pathname}${filtersQuery()}` }}>{displayName}</Link></h3>
              <div className="developer-model-public-id"><code title={model.id}>{model.id}</code><button type="button" className="icon-button model-copy-button" aria-label={`Copy model ID ${model.id}`} onClick={() => { void copyId(model.id); }}>{copiedId === model.id ? <Check size={15} aria-hidden="true" /> : <Copy size={15} aria-hidden="true" />}</button></div>
              <div className="model-capability-list">{model.capabilities.map((item) => <span className="model-capability" key={item}>{item}</span>)}</div>
              <div className="developer-model-card-prices">
                <div><span>Input</span><strong>{model.pricingVerified ? formatUsd(model.inputUsdPerMillion) : "Price not verified"}</strong><small>USD / 1M tokens</small></div>
                <div><span>Output</span><strong>{model.pricingVerified ? formatUsd(model.outputUsdPerMillion) : "Price not verified"}</strong><small>USD / 1M tokens</small></div>
                {model.pricingVerified && model.cacheUsdPerMillion != null && <div className="model-cache-rate"><span>Cached input</span><strong>{formatUsd(model.cacheUsdPerMillion)}</strong><small>USD / 1M tokens</small></div>}
              </div>
              <div className="developer-model-card-footer"><span className="pricing-provenance">{model.pricingVerified ? `Verified · ${model.priceSource ?? "source not reported"}` : "Pricing not verified"}</span>{model.activeRouteCount != null && <span className="model-route-count">{model.activeRouteCount} active {model.activeRouteCount === 1 ? "route" : "routes"}</span>}</div>
            </article>;
          })}</div>
          {entries.length > INITIAL_GROUP_SIZE && <button type="button" className="button button-quiet button-small model-group-toggle" aria-expanded={expanded} onClick={() => toggleProvider(name)}>{expanded ? "Show less" : `Show all ${entries.length} models`}</button>}
        </section>;
      })}</div> : <div className="empty-state"><div><h3>{models.length ? "No models match" : "No published models yet"}</h3><p>{models.length ? "Change the filters to see more of your provider catalog." : "Models appear here after the operator verifies their price and publishes them."}</p></div></div>}
    </section>
  </>;
}

function compareDecimal(left: string | null, right: string | null): number {
  if (left == null) return right == null ? 0 : 1;

  if (right == null) return -1;

  const parts = [left, right].map((value) => value.split("."));
  const scale = Math.max(parts[0][1]?.length ?? 0, parts[1][1]?.length ?? 0);
  const values = parts.map(([whole, fraction = ""]) => BigInt(whole) * 10n ** BigInt(scale) + BigInt(fraction.padEnd(scale, "0") || "0"));

  return values[0] < values[1] ? -1 : values[0] > values[1] ? 1 : 0;
}
