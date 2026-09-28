import { useMemo, useState } from "react";
import { PixelIcon } from "../icons/PixelIcon";
import type { ModelRecord } from "../../contracts/api";
import { formatUsd } from "../../lib/money";

export function ModelAccessPicker({ models, loading = false, error = null, onRetry, mode, selectedModelIds, onModeChange, onSelectedChange }: {
  models: ModelRecord[];
  loading?: boolean;
  error?: string | null;
  onRetry?: () => void;
  mode: "all_approved" | "selected";
  selectedModelIds: string[];
  onModeChange: (mode: "all_approved" | "selected") => void;
  onSelectedChange: (modelIds: string[]) => void;
}) {
  const [search, setSearch] = useState("");
  const matching = models.filter((model) => `${model.providerName} ${model.displayName ?? ""} ${model.id}`.toLowerCase().includes(search.toLowerCase()));

  const groups = useMemo(() => matching.reduce<Record<string, ModelRecord[]>>((result, model) => {
    (result[model.providerName] ??= []).push(model);

    return result;
  }, {}), [matching]);

  function toggleModel(modelId: string, checked: boolean) {
    onSelectedChange(checked ? [...new Set([...selectedModelIds, modelId])] : selectedModelIds.filter((item) => item !== modelId));
  }

  return <fieldset className="field-group"><legend>Model access</legend><div className="segmented-options" role="radiogroup" aria-label="Model access policy"><label className={mode === "all_approved" ? "selected" : ""}><input type="radio" name="model-access-mode" value="all_approved" checked={mode === "all_approved"} onChange={() => onModeChange("all_approved")} /><span>All published models</span></label><label className={mode === "selected" ? "selected" : ""}><input type="radio" name="model-access-mode" value="selected" checked={mode === "selected"} onChange={() => onModeChange("selected")} /><span>Choose specific models</span></label></div><p className="field-help">New keys default to all published models. Selecting models creates a fixed provider-scoped allowlist.</p>
    {mode === "selected" && <div className="model-checklist"><label className="search-field"><PixelIcon name="search" /><span className="sr-only">Search models</span><input value={search} onChange={(event) => setSearch(event.target.value)} placeholder="Search providers or models" /></label>{loading ? <p role="status" className="field-help">Loading published models…</p> : error ? <div className="inline-notice notice-error" role="alert">{error}{onRetry && <button className="button button-small" type="button" onClick={onRetry}>Retry</button>}</div> : Object.entries(groups).length ? Object.entries(groups).sort(([left], [right]) => left.localeCompare(right)).map(([providerName, entries]) => <fieldset key={providerName} className="provider-model-group"><legend>{providerName}</legend>{entries.map((model) => <label className="model-check-row" key={model.id}><input type="checkbox" checked={selectedModelIds.includes(model.id)} onChange={(event) => toggleModel(model.id, event.target.checked)} /><span><strong>{model.displayName ?? model.id}</strong><small className="mono">{model.id}</small><small>{model.capabilities.join(" · ")} · {formatUsd(model.inputUsdPerMillion)} input / 1M</small></span></label>)}</fieldset>) : <p className="field-help">No published models match this search.</p>}</div>}
  </fieldset>;
}
