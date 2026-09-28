import { NavLink } from "react-router-dom";
import { ArrowRight, ExternalLink } from "lucide-react";
import { api } from "../../lib/api";
import { useLoad } from "../shared";
import { QuickstartExample } from "./QuickstartExample";

export function QuickstartPage() {
  const models = useLoad(api.listModels);
  const base = `${window.location.origin}/v1`;

  return <>
    <header className="page-header"><div><h1>Quickstart</h1><p>Use your sponsored key with any OpenAI-compatible client.</p></div></header>
    <div className="quickstart-layout"><div><ol className="steps-list"><li><span>1</span><div><strong>Create an API key</strong><p>Choose all approved models or pick a subset. The secret is shown once.</p><NavLink className="text-link" to="/developer/keys">Open API keys <ArrowRight size={14} /></NavLink></div></li><li><span>2</span><div><strong>Set your client endpoint</strong><p>Base URL for compatible clients:</p><code className="endpoint-value">{base}</code></div></li><li><span>3</span><div><strong>Choose an approved model</strong><p>Select a model from the published catalog before you send a request.</p><NavLink className="text-link" to="/developer/models">Browse models <ArrowRight size={14} /></NavLink></div></li></ol><QuickstartExample models={models.value ?? []} loading={models.loading} /></div><aside className="quickstart-aside"><section className="section-block"><h2>What gets tracked</h2><p>Request totals, reported token counts, latency, result, and estimated or provider-reported cost.</p><p>Prompts and completions are not stored.</p></section><section className="section-block"><h2>Usage truth</h2><p>Missing provider token or cost data is shown as “Not reported,” never as zero or free.</p></section><a className="text-link" href="/docs" target="_blank" rel="noreferrer">API documentation <ExternalLink size={14} /></a></aside></div>
  </>;
}
