import { useState } from "react";
import { NavLink } from "react-router-dom";
import { Activity, ArrowRight, Boxes, ChartNoAxesColumn, Code2, Copy, KeyRound, Plus, Users } from "lucide-react";
import { ApiError, api } from "../../lib/api";
import { dateTime } from "../../lib/format";
import { ActivitySection, DataNotice, EmptyState, LoadingLine, PageHeader, StatStrip, StatusLabel, useLoad } from "../shared";
import { AllowanceSummary } from "./AllowanceSummary";
import { KeyTable } from "./KeyTable";
import { QuickstartExample } from "./QuickstartExample";

export function DeveloperHome() {
  const data = useLoad(() => api.getDeveloperDashboard(), [api]);
  const models = useLoad(api.listModels);
  const dash = data.value;

  return <>
    <PageHeader title="Home" description="Your sponsored usage, approved models, and API keys." />
    <DataNotice error={data.error} onRetry={data.reload} developer />
    {data.loading ? <LoadingLine /> : <StatStrip usage={dash?.usage ?? null} developer />}
    <nav className="developer-quick-links" aria-label="Developer shortcuts">
      <NavLink to="/developer/keys"><KeyRound size={16} aria-hidden="true" /><span><strong>API keys</strong><small>Create and manage the keys your apps authenticate with.</small></span><ArrowRight size={14} aria-hidden="true" /></NavLink>
      <NavLink to="/developer/models"><Boxes size={16} aria-hidden="true" /><span><strong>Models</strong><small>Browse the approved language, image, and embedding models.</small></span><ArrowRight size={14} aria-hidden="true" /></NavLink>
      <NavLink to="/developer/activity"><Activity size={16} aria-hidden="true" /><span><strong>Activity</strong><small>See your recent requests, token usage, and errors.</small></span><ArrowRight size={14} aria-hidden="true" /></NavLink>
      <NavLink to="/developer/analytics"><ChartNoAxesColumn size={16} aria-hidden="true" /><span><strong>Analytics</strong><small>Graphs for requests, tokens, and spend by period.</small></span><ArrowRight size={14} aria-hidden="true" /></NavLink>
      <NavLink to="/developer/quickstart"><Code2 size={16} aria-hidden="true" /><span><strong>Quickstart</strong><small>Make your first OpenAI-compatible request.</small></span><ArrowRight size={14} aria-hidden="true" /></NavLink>
    </nav>
    <div className="content-grid home-grid">
      <AllowanceSummary allowance={dash?.allowance ?? null} />
      <QuickstartExample models={models.value ?? []} loading={models.loading} />
      <section className="section-block developer-key-preview"><div className="section-heading"><div><h2>API keys</h2><p>Only keys issued to your account.</p></div><NavLink className="text-link" to="/developer/keys">Manage <ArrowRight size={15} /></NavLink></div>
        {data.loading ? <LoadingLine /> : dash?.keys.length ? <KeyTable keys={dash.keys.slice(0, 4)} /> : <EmptyState title="No keys yet" body="Create a key to use approved models through the OpenAI-compatible endpoint." action={<NavLink className="button button-secondary" to="/developer/keys">Create an API key <ArrowRight size={15} /></NavLink>} compact developer />}
      </section>
      <ActivitySection rows={dash?.recentActivity ?? []} loading={data.loading} error={data.error} developer />
      <DeveloperInviteCard />
    </div>
  </>;
}

export function DeveloperInviteCard() {
  const status = useLoad(api.getDeveloperInvites);
  const [token, setToken] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [copied, setCopied] = useState(false);
  const [creating, setCreating] = useState(false);
  const invite = status.value?.invite;
  const url = token ? `${window.location.origin}/auth/login#invite=${encodeURIComponent(token)}` : "";

  async function createInvite() {
    setCreating(true);
    setError(null);

    try {
      const result = await api.createDeveloperInvite();

      setToken(result.invite_token);
      status.reload();
    } catch (caught) {
      setError(caught instanceof ApiError ? caught.message : "The invitation could not be created.");
    } finally {
      setCreating(false);
    }
  }

  async function copyInvite() {
    try {
      await navigator.clipboard.writeText(url);
      setCopied(true);
    } catch {
      setError("Clipboard access failed. Select and copy the invitation link manually.");
    }
  }

  return <section className="section-block developer-invite" aria-labelledby="developer-invite-title">
    <div className="section-heading"><div><h2 id="developer-invite-title">Your invite</h2><p>Each developer can issue one invite. Its safe status remains after the link is gone.</p></div><Users size={18} aria-hidden="true" /></div>
    {status.loading ? <LoadingLine /> : status.error ? <p className="inline-notice notice-error" role="alert">{status.error}</p> : token
      ? <div className="created-key-state"><p className="inline-notice notice-success">Invitation created. The link is shown only now; save it before leaving this page.</p><label className="field-label" htmlFor="developer-invite-link">Invitation link</label><div className="secret-field"><input id="developer-invite-link" className="mono" readOnly value={url} /><button className="button button-secondary" type="button" onClick={() => { void copyInvite(); }}><Copy size={15} />{copied ? "Copied" : "Copy"}</button></div></div>
      : invite ? <div className="invite-status"><StatusLabel status={invite.status} /><p>Created {dateTime(invite.created_at)} · {invite.uses_count}/{invite.max_uses} uses · expires {dateTime(invite.expires_at)}</p><p>The raw link is not available after leaving this page.</p></div>
        : status.value?.can_issue ? <button className="button button-secondary" type="button" disabled={creating} onClick={() => { void createInvite(); }}><Plus size={15} />{creating ? "Creating…" : "Create invite"}</button> : <p>Your one-time invite has already been issued.</p>}
    {error && <p className="auth-error" role="alert">{error}</p>}
  </section>;
}
