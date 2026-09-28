import { useState } from "react";
import { Code2, Copy } from "lucide-react";
import type { ModelRecord } from "../../contracts/api";
import { LoadingLine } from "../shared";
import { SelectMenu } from "../SelectMenu";

export function QuickstartExample({ models, loading }: { models: ModelRecord[]; loading: boolean }) {
  const available = models.filter((model) => model.approved && model.available);
  const [selectedId, setSelectedId] = useState("");
  const [copied, setCopied] = useState(false);
  const [copyError, setCopyError] = useState("");
  const modelId = available.some((model) => model.id === selectedId) ? selectedId : available[0]?.id ?? "YOUR_APPROVED_MODEL_ID";
  const snippet = `curl ${window.location.origin}/v1/chat/completions -H "Authorization: Bearer YOUR_SPONSORED_KEY" -H "Content-Type: application/json" -d '{"model":"${modelId}","messages":[{"role":"user","content":"Hello"}]}'`;

  async function copyExample() {
    try {
      await navigator.clipboard.writeText(snippet);
      setCopied(true);
      setCopyError("");
    } catch {
      setCopied(false);
      setCopyError("Clipboard access failed. Select and copy the example manually.");
    }
  }

  return <section className="section-block quickstart-example" aria-labelledby="first-call-title">
    <div className="section-heading"><div><h2 id="first-call-title">Make your first request</h2><p>OpenAI-compatible endpoint · use your own sponsored key.</p></div><Code2 size={18} aria-hidden="true" /></div>
    {available.length > 0 && <div className="quickstart-model"><span id="quickstart-model-label">Model ID</span><SelectMenu ariaLabel="Quickstart model" value={modelId} onValueChange={(next) => { setSelectedId(next); setCopied(false); }} options={available.map((model) => ({ value: model.id, label: `${model.providerName} · ${model.id}` }))} /></div>}
    {loading && <LoadingLine />}
    {!loading && available.length === 0 && <p className="field-help">No approved model is available here. Choose an approved model from the catalog before sending a request.</p>}
    <pre className="code-block"><code>{snippet}</code><button type="button" className="button button-secondary copy-code" onClick={() => { void copyExample(); }}><Copy size={14} />{copied ? "Copied" : "Copy example"}</button></pre>
    <span className="sr-only" aria-live="polite">{copied ? "Request example copied" : copyError}</span>
    {copyError && <p className="inline-notice notice-error" role="alert">{copyError}</p>}
  </section>;
}
