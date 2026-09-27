import { useEffect, useState } from "react";
import { BrowserRouter, NavLink, Navigate, Route, Routes, useLocation, useNavigate } from "react-router-dom";
import * as Dialog from "@radix-ui/react-dialog";
import * as Tabs from "@radix-ui/react-tabs";
import {
  Activity, ArrowRight, BadgeCheck, Ban, Boxes, ChartNoAxesColumn,
  ChevronDown, CircleHelp, Clock3, Code2, Copy, ExternalLink, Gauge, KeyRound, LayoutDashboard,
  LockKeyhole, LogOut, Menu, Network, Plus, Search, Shield, ShieldAlert, SlidersHorizontal,
  Users, Wallet, X,
} from "lucide-react";
import { api, ApiError } from "../lib/api";
import { getLayoutPreviewRole } from "../lib/preview";
import { AuthPage } from "./AuthPage";
import { ProviderListPage } from "./operator/providers/ProviderListPage";
import { OperatorUsagePage as OperatorUsageSurface } from "./operator/usage/OperatorUsagePage";
import { AllowanceDialog } from "./operator/people/AllowanceEditor";
import { formatUsd, remainingUsd } from "../lib/money";
import { AllowanceSummary } from "./developer/AllowanceSummary";
import { ModelCatalogPage as ModelCatalogSurface } from "./developer/ModelCatalogPage";
import { DeveloperActivityPage as DeveloperActivitySurface } from "./developer/DeveloperActivityPage";
import { ModelAccessPicker } from "./developer/ModelAccessPicker";
import { MoneyRunway } from "./operator/MoneyRunway";
import { count, dateTime, money, tokens } from "../lib/format";
import type {
  ActivityEvent, ApiKeyRecord, CreateKeyInput, CreateKeyResult, InviteRecord, ModelRecord, ModelUsageRecord, UsagePoint,
  PersonRecord, ProviderRecord, UsageSummary,
} from "../contracts/api";

type PortalRole = "developer" | "operator";

type SessionState =
  | { status: "loading" }
  | { status: "preview"; role: PortalRole }
  | { status: "ready"; role: PortalRole; displayName: string; email: string | null }
  | { status: "error"; message: string };

interface LoadResult<T> {
  value: T | null;
  error: string | null;
  loading: boolean;
  reload: () => void;
}

function isPortalRole(value: string): value is PortalRole {
  return value === "developer" || value === "operator";
}

const developerNav = [
  { path: "/developer", label: "Home", icon: LayoutDashboard, end: true },
  { path: "/developer/keys", label: "API keys", icon: KeyRound },
  { path: "/developer/models", label: "Models", icon: Boxes },
  { path: "/developer/activity", label: "Activity", icon: Activity },
  { path: "/developer/quickstart", label: "Quickstart", icon: Code2 },
];

const operatorNav = [
  { path: "/operator", label: "Overview", icon: LayoutDashboard, end: true },
  { path: "/operator/people", label: "People & keys", icon: Users },
  { path: "/operator/providers", label: "Providers & models", icon: Network },
  { path: "/operator/usage", label: "Usage", icon: ChartNoAxesColumn },
  { path: "/operator/guardrails", label: "Guardrails & audit", icon: Shield },
];

function usePortalSession(): SessionState {
  const [session, setSession] = useState<SessionState>({ status: "loading" });
  const location = useLocation();

  useEffect(() => {
    let current = true;

    const previewRole = getLayoutPreviewRole();

    if (previewRole) {
      setSession({ status: "preview", role: previewRole });

      return () => { current = false; };
    }

    api.getSession().then((result) => {
      if (current) setSession({ status: "ready", role: result.role, displayName: result.user.displayName, email: result.user.email });
    }).catch(() => {
      if (!current) return;

      setSession({ status: "error", message: "Could not load your account session. Check portal setup, sign in again, or contact the operator." });
    });

    return () => { current = false; };
  }, [location.search]);

  return session;
}

export function App() {
  return <BrowserRouter><PortalApp /></BrowserRouter>;
}

function PortalApp() {
  const location = useLocation();

  if (location.pathname === "/auth/login") return <AuthPage />;

  return <AuthenticatedPortal />;
}

function AuthenticatedPortal() {
  const session = usePortalSession();
  const location = useLocation();
  const requestedRole: PortalRole = location.pathname.startsWith("/operator") ? "operator" : "developer";
  const role = session.status === "ready" || session.status === "preview" ? session.role : requestedRole;

  if (session.status === "loading") return <main className="session-screen" aria-live="polite"><div className="session-mark"><Gauge size={20} /> Provider Console</div><p>Checking your session…</p></main>;

  if (session.status === "error") return <main className="session-screen"><div className="session-mark"><LockKeyhole size={20} /> Provider Console</div><h1>Sign-in required</h1><p>{session.message}</p><a className="button button-primary" href="/auth/login">Sign in <ArrowRight size={16} /></a></main>;

  if (session.status === "ready" && requestedRole !== session.role) return <Navigate to={session.role === "operator" ? "/operator" : "/developer"} replace />;

  return <PortalShell role={role} preview={session.status === "preview"} userName={session.status === "ready" ? session.displayName : null} />;
}

function PortalShell({ role, preview, userName }: { role: PortalRole; preview: boolean; userName: string | null }) {
  const navigate = useNavigate();
  const [mobileOpen, setMobileOpen] = useState(false);
  const nav = role === "operator" ? operatorNav : developerNav;
  const title = role === "operator" ? "Operator" : "Developer";
  const canSwitchWorkspace = preview;
  const path = useLocation().pathname;

  useEffect(() => setMobileOpen(false), [path]);

  function switchRole(event: React.ChangeEvent<HTMLSelectElement>) {
    const target = event.currentTarget.value;

    if (!isPortalRole(target)) return;
    navigate(target === "operator" ? "/operator?preview=operator" : "/developer?preview=developer");
  }

  return <div className="app-frame">
    <a href="#main-content" className="skip-link">Skip to content</a>
    <header className="portal-header">
      <div className="portal-header-inner">
        <a className="brand" href={role === "operator" ? "/operator" : "/developer"}>
          <span className="brand-symbol"><Gauge size={17} strokeWidth={2.2} /></span>
          <span>provider<span className="brand-dot">.</span></span>
        </a>
        <span className="workspace-context">{title}</span>
        {canSwitchWorkspace && <div className="portal-select-wrap"><label className="sr-only" htmlFor="portal-select">Workspace</label>
          <select id="portal-select" value={role} onChange={switchRole} aria-label="Choose portal">
            <option value="developer">Developer portal</option>
            <option value="operator">Operator portal</option>
          </select>
          <ChevronDown size={14} aria-hidden="true" />
        </div>}
        <nav className="primary-nav" aria-label="Primary navigation">
          {nav.map((item) => <NavLink key={item.path} to={item.path} end={item.end} className={({ isActive }) => `nav-link${isActive ? " is-active" : ""}`}>
            <item.icon size={17} strokeWidth={1.8} aria-hidden="true" /> <span>{item.label}</span>
          </NavLink>)}
        </nav>
        <div className="account-row">
          <span className="account-avatar" aria-hidden="true">{userName ? userName.slice(0, 1).toUpperCase() : "P"}</span>
          <span className="account-copy"><strong>{userName ?? "Layout preview"}</strong><small>{preview ? "No account data" : title + " access"}</small></span>
          {preview ? <CircleHelp size={16} aria-label="Preview only" /> : <button className="icon-button" type="button" aria-label="Sign out" onClick={() => { void api.logout().then(() => window.location.assign("/")).catch(() => window.location.reload()); }}><LogOut size={16} /></button>}
        </div>
      </div>
    </header>

    <div className="mobile-topbar">
      <a className="brand" href={role === "operator" ? "/operator" : "/developer"}><span className="brand-symbol"><Gauge size={17} /></span><span>provider<span className="brand-dot">.</span></span></a>
      <span className="mobile-workspace-context">{title}{userName ? ` · ${userName}` : ""}</span>
      <Dialog.Root open={mobileOpen} onOpenChange={setMobileOpen}>
        <Dialog.Trigger asChild><button type="button" className="icon-button mobile-menu-button" aria-label="Open navigation"><Menu size={19} /></button></Dialog.Trigger>
        <Dialog.Portal>
          <Dialog.Overlay className="dialog-overlay" />
          <Dialog.Content className="mobile-nav-sheet">
            <div className="sheet-heading"><Dialog.Title>Navigation</Dialog.Title><Dialog.Close asChild><button className="icon-button" aria-label="Close navigation"><X size={18} /></button></Dialog.Close></div>
            {canSwitchWorkspace && <><label className="portal-label" htmlFor="mobile-portal">Workspace</label><div className="portal-select-wrap"><select id="mobile-portal" value={role} onChange={switchRole}><option value="developer">Developer portal</option><option value="operator">Operator portal</option></select><ChevronDown size={14} /></div></>}
            <nav className="sheet-nav">{nav.map((item) => <NavLink key={item.path} to={item.path} end={item.end} className={({ isActive }) => `nav-link${isActive ? " is-active" : ""}`}><item.icon size={17} /><span>{item.label}</span></NavLink>)}</nav>
            <Dialog.Description className="muted-copy">{preview ? "Layout preview only. No account data is loaded." : `Signed in as ${userName ?? "your account"}.`}</Dialog.Description>
            {!preview && <button className="button button-quiet mobile-signout" type="button" onClick={() => { void api.logout().then(() => window.location.assign("/")).catch(() => window.location.reload()); }}><LogOut size={16} /> Sign out</button>}
          </Dialog.Content>
        </Dialog.Portal>
      </Dialog.Root>
    </div>

    <main id="main-content" className="main-content">
      {preview && <div className="preview-notice"><CircleHelp size={15} /><span>Layout preview · portal data is not connected, so no usage, keys, or models are shown.</span></div>}
      <Routes>
        <Route path="/" element={<Navigate to={role === "operator" ? "/operator" : "/developer"} replace />} />
        <Route path="/developer" element={<DeveloperHome />} />
        <Route path="/developer/keys" element={<KeysPage />} />
        <Route path="/developer/models" element={<ModelsPage />} />
        <Route path="/developer/activity" element={<ActivityPage />} />
        <Route path="/developer/quickstart" element={<QuickstartPage />} />
        <Route path="/operator" element={<OperatorOverview />} />
        <Route path="/operator/people" element={<PeoplePage />} />
        <Route path="/operator/providers" element={<ProvidersPage />} />
        <Route path="/operator/usage" element={<OperatorUsageSurface portalApi={api} />} />
        <Route path="/operator/guardrails" element={<GuardrailsPage />} />
        <Route path="*" element={<NotFound />} />
      </Routes>
      <footer className="page-footer"><span>Sponsored Provider</span><span>OpenAI-compatible gateway</span></footer>
    </main>
  </div>;
}

function PageHeader({ title, description, action }: { title: string; description: string; action?: React.ReactNode }) {
  return <header className="page-header"><div><h1>{title}</h1><p>{description}</p></div>{action && <div className="page-header-action">{action}</div>}</header>;
}

function StatStrip({ usage }: { usage: UsageSummary | null }) {
  if (!usage) return <EmptyState title="Usage data isn’t connected" body="No usage figures are available from the portal API yet. This view will never substitute sample numbers." compact />;

  const rows = [
    ["Requests", count(usage.requests), `${count(usage.successfulRequests)} successful · ${count(usage.rejectedRequests)} rejected`],
    ["Input / output", `${count(usage.inputTokens)} / ${count(usage.outputTokens)}`, "Reported tokens"],
    ["Total tokens", tokens(usage.totalTokens), "Reported total"],
    ["Estimated spend", usage.estimatedSpendUsd == null ? "Not reported" : formatUsd(usage.estimatedSpendUsd), usage.source === "provider_reported" ? "Provider reported" : usage.source === "mixed" ? "Mixed source" : "Gateway estimate"],
  ];

  return <div className="stat-strip" aria-label="Usage summary">{rows.map(([label, value, context], index) => <div className={`stat-cell${index === 0 ? " stat-cell-primary" : ""}`} key={label}><span>{label}</span><strong>{value}</strong><small>{context}</small></div>)}</div>;
}

function DataNotice({ error, onRetry }: { error: string | null; onRetry?: () => void }) {
  if (!error) return null;

  return <div className="inline-notice notice-error" role="alert"><ShieldAlert size={17} /><span>{error}</span>{onRetry && <button type="button" className="button button-small" onClick={onRetry}>Retry</button>}</div>;
}

function EmptyState({ title, body, action, compact = false }: { title: string; body: string; action?: React.ReactNode; compact?: boolean }) {
  return <div className={`empty-state${compact ? " empty-compact" : ""}`}><span className="empty-mark"><CircleHelp size={19} /></span><div><h3>{title}</h3><p>{body}</p>{action && <div className="empty-action">{action}</div>}</div></div>;
}

function MetricPanel({ usage, series }: { usage: UsageSummary | null; series: UsagePoint[] }) {
  const [metric, setMetric] = useState("requests");

  const selected = series.map((point) => ({
    point,
    value: metric === "requests" ? point.requests : metric === "tokens" ? point.total_tokens : point.estimated_spend_usd,
  }));

  const largest = Math.max(0, ...selected.map((entry) => entry.value == null ? 0 : Number(entry.value)));
  const metricName = metric === "requests" ? "Requests" : metric === "tokens" ? "Tokens" : "Estimated spend";

  function valueText(value: number | string | null) {
    if (value == null) return "Not reported";

    return metric === "spend" ? formatUsd(String(value)) : count(Number(value));
  }

  return <section className="section-block"><div className="section-heading"><div><h2>Usage trend</h2><p>{usage ? `Last 14 days · ${metricName} · gateway-reported activity` : "Trend will appear when usage data is available."}</p></div><Tabs.Root value={metric} onValueChange={setMetric} className="metric-tabs"><Tabs.List aria-label="Usage trend unit"><Tabs.Trigger value="requests">Requests</Tabs.Trigger><Tabs.Trigger value="tokens">Tokens</Tabs.Trigger><Tabs.Trigger value="spend">Spend</Tabs.Trigger></Tabs.List></Tabs.Root></div>
    {selected.length ? <div className="usage-chart-wrap"><div className="usage-bars" role="img" aria-label={`${metricName} over the last ${selected.length} days`}>{selected.map(({ point, value }) => { const height = largest > 0 && value != null ? Math.max(2, Number(value) / largest * 100) : 0;

 return <div className="usage-bar-column" key={point.day} title={`${point.day}: ${valueText(value)}`}><span className="usage-bar-value">{valueText(value)}</span><span className="usage-bar" style={{ height: `${height}%` }} /><time dateTime={point.day}>{point.day.slice(5)}</time></div>; })}</div><table className="sr-only"><caption>{metricName} by day</caption><thead><tr><th>Date</th><th>{metricName}</th></tr></thead><tbody>{selected.map(({ point, value }) => <tr key={point.day}><td>{point.day}</td><td>{valueText(value)}</td></tr>)}</tbody></table></div> : <div className="chart-placeholder"><ChartNoAxesColumn size={21} /><span>No usage data yet</span><small>The chart will fill from recorded request events.</small></div>}
  </section>;
}

function ModelUsagePanel({ models, loading }: { models: ModelUsageRecord[]; loading: boolean }) {
  return <section className="section-block model-usage-panel"><div className="section-heading"><div><h2>Models in use</h2><p>Request count, reported tokens, and local cost estimate.</p></div><Boxes size={18} /></div>{loading ? <LoadingLine /> : models.length ? <div className="table-scroll"><table><thead><tr><th>Model</th><th>Provider</th><th>Requests</th><th>Tokens</th><th>Estimated spend</th></tr></thead><tbody>{models.map((model) => <tr key={model.modelId}><td><strong className="mono">{model.modelId}</strong></td><td>{model.providerName}</td><td>{count(model.requests)}</td><td>{model.totalTokens == null ? "Not reported" : count(model.totalTokens)}</td><td>{model.estimatedSpendUsd == null ? "Not reported" : formatUsd(model.estimatedSpendUsd)}</td></tr>)}</tbody></table></div> : <EmptyState title="No model usage yet" body="Real requests will add models here. No sample usage is shown." compact />}</section>;
}

function useLoad<T>(loader: () => Promise<T>, dependencies: React.DependencyList = []): LoadResult<T> {
  const [value, setValue] = useState<T | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [reloadIndex, setReloadIndex] = useState(0);
  const reload = () => setReloadIndex((previous) => previous + 1);
  const previewRole = getLayoutPreviewRole();
  useEffect(() => {
    if (previewRole) {
      setValue(null);
      setError(null);
      setLoading(false);

      return;
    }

    let active = true;
    setLoading(true);
    setError(null);

    async function fetchPage() {
      try {
        const result = await loader();

        if (active) setValue(result);
      } catch {
        if (active) setError("The portal API could not load this data. Retry or contact the operator.");
      } finally {
        if (active) setLoading(false);
      }
    }

    void fetchPage();

    return () => { active = false; };
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [...dependencies, previewRole, reloadIndex]);

  return { value, error, loading, reload };
}

function LoadingLine() { return <div className="loading-line" role="status"><span className="sr-only">Loading</span></div>; }

function DeveloperHome() {
  const data = useLoad(api.getDeveloperDashboard);
  const models = useLoad(api.listModels);
  const dash = data.value;

  return <>
    <PageHeader title="Home" description="Your sponsored usage, approved models, and API keys." />
    <DataNotice error={data.error} onRetry={data.reload} />
    {data.loading ? <LoadingLine /> : <StatStrip usage={dash?.usage ?? null} />}
    <nav className="developer-quick-links" aria-label="Developer shortcuts">
      <NavLink to="/developer/keys"><KeyRound size={16} /> API keys <ArrowRight size={14} /></NavLink>
      <NavLink to="/developer/models"><Boxes size={16} /> Models <ArrowRight size={14} /></NavLink>
      <NavLink to="/developer/activity"><Activity size={16} /> Activity <ArrowRight size={14} /></NavLink>
      <NavLink to="/developer/quickstart"><Code2 size={16} /> Quickstart <ArrowRight size={14} /></NavLink>
    </nav>
    <div className="content-grid home-grid">
      <AllowanceSummary allowance={dash?.allowance ?? null} />
      <QuickstartExample models={models.value ?? []} loading={models.loading} />
      <MetricPanel usage={dash?.usage ?? null} series={dash?.series ?? []} />
      <section className="section-block"><div className="section-heading"><div><h2>API keys</h2><p>Only keys issued to your account.</p></div><NavLink className="text-link" to="/developer/keys">Manage <ArrowRight size={15} /></NavLink></div>
        {data.loading ? <LoadingLine /> : dash?.keys.length ? <KeyTable keys={dash.keys.slice(0, 4)} /> : <EmptyState title="No keys yet" body="Create a key to use approved models through the OpenAI-compatible endpoint." action={<NavLink className="button button-secondary" to="/developer/keys">Create an API key <ArrowRight size={15} /></NavLink>} compact />}
      </section>
      <ActivitySection rows={dash?.recentActivity ?? []} loading={data.loading} error={data.error} developer />
      <DeveloperInviteCard />
    </div>
    <ModelUsagePanel models={dash?.topModels ?? []} loading={data.loading} />
  </>;
}

function QuickstartExample({ models, loading }: { models: ModelRecord[]; loading: boolean }) {
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
    {available.length > 0 && <label className="quickstart-model"><span>Model ID</span><select aria-label="Quickstart model" value={modelId} onChange={(event) => { setSelectedId(event.target.value); setCopied(false); }}>
      {available.map((model) => <option value={model.id} key={model.id}>{model.providerName} · {model.id}</option>)}
    </select></label>}
    {loading && <LoadingLine />}
    {!loading && available.length === 0 && <p className="field-help">No approved model is available here. Choose an approved model from the catalog before sending a request.</p>}
    <pre className="code-block"><code>{snippet}</code><button type="button" className="button button-secondary copy-code" onClick={() => { void copyExample(); }}><Copy size={14} />{copied ? "Copied" : "Copy example"}</button></pre>
    <span className="sr-only" aria-live="polite">{copied ? "Request example copied" : copyError}</span>
    {copyError && <p className="inline-notice notice-error" role="alert">{copyError}</p>}
  </section>;
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
    setCreating(true); setError(null);

    try {
      const result = await api.createDeveloperInvite();

      setToken(result.invite_token);
      status.reload();
    } catch (caught) {
      setError(caught instanceof ApiError ? caught.message : "The invitation could not be created.");
    } finally { setCreating(false); }
  }

  async function copyInvite() {
    try { await navigator.clipboard.writeText(url); setCopied(true); }
    catch { setError("Clipboard access failed. Select and copy the invitation link manually."); }
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

function AllowanceRunway({ allowance }: { allowance: { usedUsd: number | null; limitUsd: number | null; period: string | null; resetAt: string | null } | null }) {
  const percent = allowance?.usedUsd != null && allowance.limitUsd != null && allowance.limitUsd > 0 ? Math.min(100, allowance.usedUsd / allowance.limitUsd * 100) : null;

  return <div className="runway"><div className="runway-values"><span>{allowance?.usedUsd == null ? "Usage not reported" : `${money(allowance.usedUsd)} used`}</span><strong>{allowance?.limitUsd == null ? "Limit not assigned" : `${money(allowance.limitUsd)} ${allowance.period ?? "period"}`}</strong></div><div className="runway-track" role="progressbar" aria-label="Allowance used" aria-valuemin={0} aria-valuemax={100} aria-valuenow={percent == null ? undefined : Math.round(percent)}><span style={{ transform: `scaleX(${percent == null ? 0 : percent / 100})` }} /></div><p>{allowance?.resetAt ? `Resets ${dateTime(allowance.resetAt)}` : "Reset schedule unavailable"}</p></div>;
}

function KeyTable({ keys, onEdit, onRevoke, onArchive }: { keys: ApiKeyRecord[]; onEdit?: (key: ApiKeyRecord) => void; onRevoke?: (key: ApiKeyRecord) => void; onArchive?: (key: ApiKeyRecord) => void }) {
  const canManage = Boolean(onEdit || onRevoke || onArchive);

  return <div className="table-scroll"><table><thead><tr><th>Key</th><th>Models</th><th>Spend used / cap</th><th>RPM</th><th>Status</th>{canManage && <th>Actions</th>}</tr></thead><tbody>{keys.map((key) => <tr key={key.id}><td><strong>{key.label}</strong><small className="mono">{key.prefix}••••</small></td><td>{key.modelAccess.mode === "all_approved" ? "All approved" : `${key.modelAccess.modelIds.length} selected`}</td><td>{formatUsd(key.spendUsedUsd)} used{key.spendCapUsd == null ? " · no key cap" : ` / ${formatUsd(key.spendCapUsd)} ${key.spendPeriod}`}<small>{key.spendResetAt ? `Resets ${dateTime(key.spendResetAt)}` : key.spendCapUsd == null ? "No key reset" : "No reset scheduled"}</small></td><td>{key.rpmLimit == null ? "Inherited" : count(key.rpmLimit)}</td><td><StatusLabel status={key.status} /></td>{canManage && <td><div className="row-actions">{onEdit && key.status === "active" && <button type="button" className="button button-quiet button-small" onClick={() => onEdit(key)}>Edit</button>}{onRevoke && key.status === "active" && <button type="button" className="button button-quiet button-small" onClick={() => onRevoke(key)}>Revoke</button>}{onArchive && key.status !== "archived" && <button type="button" className="button button-quiet button-small" onClick={() => onArchive(key)}>Archive</button>}</div></td>}</tr>)}</tbody></table></div>;
}

function StatusLabel({ status }: { status: string }) {
  const safeStatus = status.toLowerCase();

  return <span className={`status-label status-${safeStatus}`}><span className="status-dot" />{status.replaceAll("_", " ")}</span>;
}

function KeysPage() {
  const keys = useLoad(api.listKeys);
  const [open, setOpen] = useState(false);
  const [created, setCreated] = useState<CreateKeyResult | null>(null);
  const [editing, setEditing] = useState<ApiKeyRecord | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);

  async function revokeKey(key: ApiKeyRecord) {
    if (!window.confirm(`Revoke “${key.label}”? Any client using this key will stop working immediately.`)) return;
    setActionError(null);

    try {
      await api.revokeKey(key.id);
      keys.reload();
    } catch {
      setActionError("The key could not be revoked. Try again or contact the operator.");
    }
  }

  async function archiveKey(key: ApiKeyRecord) {
    if (!window.confirm(`Archive “${key.label}”? Its usage history will be retained.`)) return;
    setActionError(null);

    try {
      await api.archiveKey(key.id);
      keys.reload();
    } catch {
      setActionError("The key could not be archived. Try again or contact the operator.");
    }
  }

  return <>
    <PageHeader title="API keys" description="Create and manage your own access keys." action={<button className="button button-primary" onClick={() => { setCreated(null); setOpen(true); }}><Plus size={16} /> Create key</button>} />
    <DataNotice error={keys.error ?? actionError} onRetry={keys.reload} />
    <section className="section-block table-section"><div className="section-heading"><div><h2>Your keys</h2><p>Secrets are shown once at creation. Existing secrets cannot be viewed again.</p></div><span className="count-label">{keys.value ? `${keys.value.length} keys` : "— keys"}</span></div>
      {keys.loading ? <LoadingLine /> : keys.value?.length ? <KeyTable keys={keys.value} onEdit={setEditing} onRevoke={revokeKey} onArchive={archiveKey} /> : <EmptyState title="No API keys found" body="Choose Create key to issue a credential for your coding agent. You can limit approved models, spend, and RPM." />}
    </section>
    <CreateKeyDialog open={open} onOpenChange={setOpen} created={created} onCreated={setCreated} onSaved={keys.reload} />
    <EditKeyDialog keyRecord={editing} onClose={() => setEditing(null)} onSaved={keys.reload} />
  </>;
}

function EditKeyDialog({ keyRecord, onClose, onSaved }: { keyRecord: ApiKeyRecord | null; onClose: () => void; onSaved: () => void }) {
  const models = useLoad(api.listModels, [Boolean(keyRecord)]);
  const [mode, setMode] = useState<"all_approved" | "selected">("all_approved");
  const [selectedModels, setSelectedModels] = useState<string[]>([]);
  const [spendCap, setSpendCap] = useState("");
  const [spendPeriod, setSpendPeriod] = useState<CreateKeyInput["spendPeriod"]>("week");
  const [rpm, setRpm] = useState("");
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    setMode(keyRecord?.modelAccess.mode ?? "all_approved");
    setSelectedModels(keyRecord?.modelAccess.mode === "selected" ? [...keyRecord.modelAccess.modelIds] : []);
    setSpendCap(keyRecord?.spendCapUsd == null ? "" : String(keyRecord.spendCapUsd));
    setSpendPeriod(keyRecord?.spendPeriod ?? "week");
    setRpm(keyRecord?.rpmLimit == null ? "" : String(keyRecord.rpmLimit));
    setError(null);
  }, [keyRecord]);

  const approvedModels = (models.value ?? []).filter((model) => model.approved && model.available && model.pricingVerified);

  async function save(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();

    if (!keyRecord) return;

    if (mode === "selected" && selectedModels.length === 0) {
      setError("Select at least one approved model, or choose all approved models.");

      return;
    }

    setSaving(true);
    setError(null);

    try {
      const period: CreateKeyInput["spendPeriod"] = spendCap.trim() ? spendPeriod : null;
      await api.updateKeyPolicy(keyRecord.id, {
        label: keyRecord.label,
        modelAccess: mode === "all_approved" ? { mode } : { mode, modelIds: selectedModels },
        spendCapUsd: spendCap.trim() ? spendCap.trim() : null,
        spendPeriod: period,
        rpmLimit: rpm.trim() ? Number(rpm) : null,
      });
      onSaved();
      onClose();
    } catch (caught) {
      setError(caught instanceof ApiError ? caught.message : "Key policy could not be updated.");
    } finally {
      setSaving(false);
    }
  }

  return <Dialog.Root open={Boolean(keyRecord)} onOpenChange={(open) => { if (!open) onClose(); }}><Dialog.Portal><Dialog.Overlay className="dialog-overlay" /><Dialog.Content className="dialog-content" aria-describedby="edit-key-description"><div className="dialog-title-row"><div><Dialog.Title>Edit key policy</Dialog.Title><Dialog.Description id="edit-key-description">{keyRecord?.label} · values can only tighten the account-level allowance.</Dialog.Description></div><Dialog.Close asChild><button className="icon-button" aria-label="Close"><X size={18} /></button></Dialog.Close></div><form onSubmit={save} className="dialog-form"><ModelAccessPicker models={approvedModels} loading={models.loading} error={models.error} onRetry={models.reload} mode={mode} selectedModelIds={selectedModels} onModeChange={setMode} onSelectedChange={setSelectedModels} /><div className="form-two-col"><label><span className="field-label">Spend cap (USD)</span><input type="number" inputMode="decimal" min="0.000000001" step="any" value={spendCap} onChange={(event) => setSpendCap(event.target.value)} placeholder="Inherit allowance" /></label><label><span className="field-label">Reset period</span><select value={spendPeriod ?? "week"} disabled={!spendCap} onChange={(event) => { const period = event.target.value; setSpendPeriod(period === "day" || period === "week" || period === "month" || period === "lifetime" ? period : "week"); }}><option value="day">Daily</option><option value="week">Weekly</option><option value="month">Monthly</option><option value="lifetime">Lifetime</option></select></label></div><label><span className="field-label">Requests per minute</span><input type="number" min="1" step="1" value={rpm} onChange={(event) => setRpm(event.target.value)} placeholder="Inherit user limit" /></label>{error && <div className="inline-notice notice-error" role="alert"><ShieldAlert size={16} /><span>{error}</span></div>}<div className="dialog-actions"><Dialog.Close asChild><button type="button" className="button button-quiet">Cancel</button></Dialog.Close><button className="button button-primary" disabled={saving}>{saving ? "Saving…" : "Save policy"}</button></div></form></Dialog.Content></Dialog.Portal></Dialog.Root>;
}

export function CreateKeyDialog({ open, onOpenChange, created, onCreated, onSaved }: { open: boolean; onOpenChange: (open: boolean) => void; created: CreateKeyResult | null; onCreated: (result: CreateKeyResult | null) => void; onSaved: () => void }) {
  const models = useLoad(api.listModels, [open]);
  const [label, setLabel] = useState("");
  const [mode, setMode] = useState<"all_approved" | "selected">("all_approved");
  const [selectedModels, setSelectedModels] = useState<string[]>([]);
  const [spendCap, setSpendCap] = useState("");
  const [spendPeriod, setSpendPeriod] = useState("week");
  const [rpm, setRpm] = useState("");
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [copied, setCopied] = useState(false);

  useEffect(() => {
    if (open) {
      setLabel(""); setMode("all_approved"); setSelectedModels([]); setSpendCap(""); setRpm(""); setError(null); setCopied(false);
      onCreated(null);
    }
  }, [open, onCreated]);

  const approvedModels = (models.value ?? []).filter((model) => model.approved && model.available && model.pricingVerified);

  async function submit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();

    if (mode === "selected" && selectedModels.length === 0) { setError("Choose at least one approved model, or select all approved models.");

 return; }

    setSaving(true); setError(null);

    const period: CreateKeyInput["spendPeriod"] = spendCap.trim()
      ? spendPeriod === "day" || spendPeriod === "week" || spendPeriod === "month" || spendPeriod === "lifetime" ? spendPeriod : "week"
      : null;

    const payload: CreateKeyInput = {
      label: label.trim(),
      modelAccess: mode === "all_approved" ? { mode } : { mode, modelIds: selectedModels },
      spendCapUsd: spendCap.trim() ? spendCap.trim() : null,
      spendPeriod: period,
      rpmLimit: rpm.trim() ? Number(rpm) : null,
    };

    try {
      onCreated(await api.createKey(payload));
      onSaved();
    } catch {
      setError("The key could not be created. Check your policy values and try again.");
    } finally { setSaving(false); }
  }

  async function copySecret() {
    if (!created) return;

    try { await navigator.clipboard.writeText(created.secret); setCopied(true); }
    catch { setError("Clipboard access failed. Select and copy the key manually."); }
  }

  return <Dialog.Root open={open} onOpenChange={onOpenChange}>
    <Dialog.Portal><Dialog.Overlay className="dialog-overlay" /><Dialog.Content className="dialog-content" aria-describedby="create-key-description">
      <div className="dialog-title-row"><div><Dialog.Title>{created ? "Your key is ready" : "Create API key"}</Dialog.Title><Dialog.Description id="create-key-description">{created ? "Copy this secret now. It will not be shown again." : "The server enforces your account allowance and approved model policy."}</Dialog.Description></div><Dialog.Close asChild><button className="icon-button" aria-label="Close"><X size={18} /></button></Dialog.Close></div>
      {created ? <div className="created-key-state"><div className="inline-notice notice-success"><BadgeCheck size={17} /><span>Key created. The secret is visible only in this dialog.</span></div><label className="field-label" htmlFor="created-secret">API key</label><div className="secret-field"><input id="created-secret" className="mono" readOnly value={created.secret} autoComplete="off" /><button type="button" className="button button-secondary" onClick={copySecret}><Copy size={15} />{copied ? "Copied" : "Copy"}</button></div><p className="field-help">Close this dialog when you’ve stored it securely. Never commit it to a repository.</p><div className="dialog-actions"><Dialog.Close asChild><button className="button button-primary">Done</button></Dialog.Close></div></div> : <form onSubmit={submit} className="dialog-form">
        <label className="field-label" htmlFor="key-label">Key name</label><input id="key-label" required maxLength={64} autoFocus value={label} onChange={(event) => setLabel(event.target.value)} placeholder="e.g. OpenCode laptop" />
        <ModelAccessPicker models={approvedModels} loading={models.loading} error={models.error} onRetry={models.reload} mode={mode} selectedModelIds={selectedModels} onModeChange={setMode} onSelectedChange={setSelectedModels} />
        <div className="form-two-col"><div><label className="field-label" htmlFor="spend-cap">Optional spend cap (USD)</label><input id="spend-cap" type="number" inputMode="decimal" min="0.000000001" step="any" value={spendCap} onChange={(event) => setSpendCap(event.target.value)} placeholder="Inherit account allowance" /><p className="field-help">A key cap can only tighten your account allowance. Minimum: $0.000000001.</p></div><div><label className="field-label" htmlFor="spend-period">Cap reset</label><select id="spend-period" value={spendPeriod} onChange={(event) => setSpendPeriod(event.target.value)} disabled={!spendCap}><option value="day">Daily</option><option value="week">Weekly</option><option value="month">Monthly</option><option value="lifetime">Lifetime</option></select></div></div>
        <div><label className="field-label" htmlFor="key-rpm">Optional requests per minute</label><input id="key-rpm" type="number" min="1" step="1" value={rpm} onChange={(event) => setRpm(event.target.value)} placeholder="Inherit account limit" /><p className="field-help">A per-key RPM can only be lower than your user-wide limit.</p></div>
        {error && <div className="inline-notice notice-error" role="alert"><ShieldAlert size={16} /><span>{error}</span></div>}
        <div className="dialog-actions"><Dialog.Close asChild><button type="button" className="button button-quiet">Cancel</button></Dialog.Close><button type="submit" className="button button-primary" disabled={saving}>{saving ? "Creating…" : "Create key"}</button></div>
      </form>}
    </Dialog.Content></Dialog.Portal>
  </Dialog.Root>;
}

function ModelsPage() {
  return <ModelCatalogSurface portalApi={api} />;
}

function ActivityPage() {
  return <DeveloperActivitySurface portalApi={api} />;
}

function ActivityFilters({ model, onModelChange, status, onStatusChange }: { model: string; onModelChange: (value: string) => void; status: string; onStatusChange: (value: string) => void }) {
  return <div className="toolbar activity-toolbar"><label className="search-field"><Search size={16} /><span className="sr-only">Filter by model</span><input value={model} onChange={(event) => onModelChange(event.target.value)} placeholder="Filter by model" /></label><label className="select-filter"><span className="sr-only">Filter by result</span><select value={status} onChange={(event) => onStatusChange(event.target.value)}><option value="all">All results</option><option value="success">Success</option><option value="error">Error</option><option value="rejected">Rejected</option><option value="interrupted">Interrupted</option></select><ChevronDown size={14} /></label><span className="filter-note"><SlidersHorizontal size={14} /> User-scoped logs</span></div>;
}

function ActivityTable({ rows, developer }: { rows: ActivityEvent[]; developer: boolean }) {
  return <div className="table-scroll activity-table-wrap"><table><thead><tr><th>Time</th><th>Model</th><th>Tokens in / out</th><th>Cost</th><th>Result</th><th>Latency</th>{!developer && <th>Client IP</th>}</tr></thead><tbody>{rows.map((row) => <tr key={row.id}><td>{dateTime(row.occurredAt)}</td><td><strong className="mono">{row.modelId}</strong><small>{row.keyLabel}</small></td><td>{row.inputTokens == null && row.outputTokens == null ? "Usage not reported" : `${count(row.inputTokens)} / ${count(row.outputTokens)}`}<small>{row.totalTokens == null ? "Total not reported" : `${count(row.totalTokens)} total`}{row.cachedTokens != null ? ` · ${count(row.cachedTokens)} cached` : ""}</small></td><td>{row.estimatedCostUsd == null ? "Not reported" : formatUsd(row.estimatedCostUsd)}<small>{row.costSource === "gateway_estimate" ? "Gateway estimate" : row.costSource === "provider_reported" ? "Provider-reported" : "Cost unknown"}</small></td><td><StatusLabel status={row.status} />{row.errorCategory && <small>{row.errorCategory}</small>}</td><td>{row.latencyMs == null ? "Not reported" : `${count(row.latencyMs)} ms`}</td>{!developer && <td className="mono">{row.requestIp ?? "Not recorded"}</td>}</tr>)}</tbody></table></div>;
}

function ActivitySection({ rows, loading, error, developer = false }: { rows: ActivityEvent[]; loading: boolean; error: string | null; developer?: boolean }) {
  return <section className="section-block activity-preview"><div className="section-heading"><div><h2>Recent activity</h2><p>{developer ? "Your latest requests" : "Latest gateway requests"}</p></div><NavLink to={developer ? "/developer/activity" : "/operator/usage"} className="text-link">View activity <ArrowRight size={15} /></NavLink></div>
    {loading ? <LoadingLine /> : rows.length ? <ActivityTable rows={rows.slice(0, 6)} developer={developer} /> : <EmptyState title={error ? "Activity unavailable" : "No recent activity"} body={error ? "The API could not load activity records." : "No request events have been returned for this period."} compact />}
  </section>;
}

function QuickstartPage() {
  const models = useLoad(api.listModels);
  const base = `${window.location.origin}/v1`;

  return <><PageHeader title="Quickstart" description="Use your sponsored key with any OpenAI-compatible client." /><div className="quickstart-layout"><div><ol className="steps-list"><li><span>1</span><div><strong>Create an API key</strong><p>Choose all approved models or pick a subset. The secret is shown once.</p><NavLink className="text-link" to="/developer/keys">Open API keys <ArrowRight size={14} /></NavLink></div></li><li><span>2</span><div><strong>Set your client endpoint</strong><p>Base URL for compatible clients:</p><code className="endpoint-value">{base}</code></div></li><li><span>3</span><div><strong>Choose an approved model</strong><p>Select a model from the published catalog before you send a request.</p><NavLink className="text-link" to="/developer/models">Browse models <ArrowRight size={14} /></NavLink></div></li></ol><QuickstartExample models={models.value ?? []} loading={models.loading} /></div><aside className="quickstart-aside"><section className="section-block"><h2>What gets tracked</h2><p>Request totals, reported token counts, latency, result, and estimated or provider-reported cost.</p><p>Prompts and completions are not stored.</p></section><section className="section-block"><h2>Usage truth</h2><p>Missing provider token or cost data is shown as “Not reported,” never as zero or free.</p></section><a className="text-link" href="/docs" target="_blank" rel="noreferrer">API documentation <ExternalLink size={14} /></a></aside></div></>;
}

function OperatorOverview() {
  const data = useLoad(api.getOperatorDashboard);
  const dash = data.value;

  return <><PageHeader title="Overview" description="Protect the shared upstream budget and see what needs attention." action={<span className="period-chip"><Clock3 size={14} /> Current period</span>} /><DataNotice error={data.error} onRetry={data.reload} />{data.loading ? <LoadingLine /> : <StatStrip usage={dash?.usage ?? null} />}
    <div className="content-grid operator-grid"><section className="section-block runway-block"><div className="section-heading"><div><h2>Global usage runway</h2><p>Local estimate plus active reservations when provided by the API.</p></div><Wallet size={18} /></div><AllowanceRunway allowance={dash?.guardrails ? { usedUsd: dash.guardrails.globalSpendUsedUsd, limitUsd: dash.guardrails.globalSpendCapUsd, period: "global cap", resetAt: null } : null} />{dash?.guardrails && <p className="source-note">Safety reserve: {money(dash.guardrails.safetyReserveUsd)} · {dash.guardrails.globalStopped ? "Global stop is active" : "Global stop is not active"}</p>}</section><MetricPanel usage={dash?.usage ?? null} series={dash?.series ?? []} /><section className="section-block"><div className="section-heading"><div><h2>Provider health</h2><p>Connection and model-catalog freshness.</p></div><NavLink to="/operator/providers" className="text-link">Manage <ArrowRight size={15} /></NavLink></div>{data.loading ? <LoadingLine /> : dash?.providers.length ? <ProviderList providers={dash.providers} /> : <EmptyState title="No provider status available" body="Connectors will be listed after the operator API returns provider health." compact />}</section><ActivitySection rows={dash?.recentActivity ?? []} loading={data.loading} error={data.error} /></div><ModelUsagePanel models={dash?.topModels ?? []} loading={data.loading} /></>;
}

function PeoplePage() {
  const people = useLoad(api.listPeople);
  const [search, setSearch] = useState("");
  const [inviteOpen, setInviteOpen] = useState(false);
  const [createdInvite, setCreatedInvite] = useState<string | null>(null);
  const [policyPerson, setPolicyPerson] = useState<PersonRecord | null>(null);
  const [peopleActionError, setPeopleActionError] = useState<string | null>(null);
  const filtered = (people.value ?? []).filter((person) => `${person.displayName} ${person.email ?? ""}`.toLowerCase().includes(search.toLowerCase()));

  async function togglePerson(person: PersonRecord) {
    const enabling = person.status === "disabled";

    if (!enabling && !window.confirm(`Disable ${person.displayName}? Their API keys will stop working immediately.`)) return;
    setPeopleActionError(null);

    try {
      await api.setPersonEnabled(person.id, enabling);
      people.reload();
    } catch {
      setPeopleActionError("The account status could not be changed.");
    }
  }

  return <><PageHeader title="People & keys" description="Manage invitations, account allowances, and user-owned keys." action={<button className="button button-primary" onClick={() => { setCreatedInvite(null); setInviteOpen(true); }}><Plus size={16} /> Invite person</button>} /><DataNotice error={people.error ?? peopleActionError} onRetry={people.reload} /><section className="section-block table-section"><div className="toolbar"><label className="search-field"><Search size={16} /><span className="sr-only">Search people</span><input value={search} onChange={(event) => setSearch(event.target.value)} placeholder="Search people" /></label><span className="count-label">{people.value ? `${filtered.length} people` : "— people"}</span></div>{people.loading ? <LoadingLine /> : filtered.length ? <PeopleTable people={filtered} onEditPolicy={setPolicyPerson} onToggle={togglePerson} /> : <EmptyState title="No people returned" body="Create an invitation, then assign an allowance after the developer signs in." />}</section><InviteDialog open={inviteOpen} onOpenChange={setInviteOpen} token={createdInvite} setToken={setCreatedInvite} /><AllowanceDialog person={policyPerson} onClose={() => setPolicyPerson(null)} onSave={(input) => api.updatePersonPolicy(policyPerson!.id, input).then(people.reload)} /></>;
}

export function InviteDialog({ open, onOpenChange, token, setToken }: { open: boolean; onOpenChange: (open: boolean) => void; token: string | null; setToken: (token: string | null) => void }) {
  const [maxUses, setMaxUses] = useState("5");
  const [expiryDays, setExpiryDays] = useState("7");
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [copied, setCopied] = useState(false);
  const [invites, setInvites] = useState<InviteRecord[]>([]);
  const [loadingInvites, setLoadingInvites] = useState(false);
  const inviteUrl = token ? `${window.location.origin}/auth/login#invite=${encodeURIComponent(token)}` : "";

  useEffect(() => {
    if (!open) return;
    setLoadingInvites(true);
    api.listOperatorInvites().then(setInvites).catch(() => setError("Invitations could not be loaded.")).finally(() => setLoadingInvites(false));
  }, [open, token]);

  async function submit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setSaving(true);
    setError(null);

    try {
      const result = await api.createInvite({ max_uses: Number(maxUses), expires_in_seconds: Number(expiryDays) * 24 * 60 * 60 });
      setToken(result.invite_token);
      setCopied(false);
    } catch (caught) {
      setError(caught instanceof ApiError ? caught.message : "Invitation could not be created.");
    } finally {
      setSaving(false);
    }
  }

  async function copyInvite() {
    try {
      await navigator.clipboard.writeText(inviteUrl);
      setCopied(true);
    } catch {
      setError("Clipboard access failed. Select and copy the invitation link manually.");
    }
  }

  async function revoke(invite: InviteRecord) {
    if (!window.confirm(`Revoke this invitation? ${invite.uses_count}/${invite.max_uses} accounts have already used it.`)) return;

    setError(null);

    try {
      await api.revokeInvite(invite.id);
      setInvites(await api.listOperatorInvites());
    } catch { setError("The invitation could not be revoked."); }
  }

  return <Dialog.Root open={open} onOpenChange={onOpenChange}><Dialog.Portal><Dialog.Overlay className="dialog-overlay" /><Dialog.Content className="dialog-content invite-manager" aria-describedby="invite-dialog-description"><div className="dialog-title-row"><div><Dialog.Title>Invitations</Dialog.Title><Dialog.Description id="invite-dialog-description">Create local account links and manage existing invitations.</Dialog.Description></div><Dialog.Close asChild><button className="icon-button" aria-label="Close invitations"><X size={18} /></button></Dialog.Close></div>{token ? <div className="created-key-state"><div className="inline-notice notice-success"><BadgeCheck size={17} /><span>Invitation created. This raw link is visible only once. Copy it before closing.</span></div><label className="field-label" htmlFor="invite-link">Invitation link</label><div className="secret-field"><input id="invite-link" className="mono" readOnly value={inviteUrl} /><button type="button" className="button button-secondary" onClick={() => { void copyInvite(); }}><Copy size={15} />{copied ? "Copied" : "Copy"}</button></div><div className="dialog-actions"><button type="button" className="button button-primary" onClick={() => setToken(null)}>Create another</button><Dialog.Close asChild><button type="button" className="button button-quiet">Done</button></Dialog.Close></div></div> : <form className="dialog-form invite-form" onSubmit={(event) => { void submit(event); }}><div className="form-two-col"><div><label className="field-label" htmlFor="invite-max-uses">Maximum uses</label><input id="invite-max-uses" type="number" min="1" max="1000" step="1" required value={maxUses} onChange={(event) => setMaxUses(event.target.value)} /></div><div><label className="field-label" htmlFor="invite-expiry">Expires in (days)</label><input id="invite-expiry" type="number" min="1" max="30" step="1" required value={expiryDays} onChange={(event) => setExpiryDays(event.target.value)} /></div></div><p className="field-help">Defaults: five uses and seven days. Invite links are not bound to an email.</p>{error && <div className="inline-notice notice-error" role="alert"><ShieldAlert size={16} /><span>{error}</span></div>}<div className="dialog-actions"><Dialog.Close asChild><button type="button" className="button button-quiet">Close</button></Dialog.Close><button type="submit" className="button button-primary" disabled={saving}>{saving ? "Creating…" : "Create invite"}</button></div></form>}
      <section className="invite-list" aria-labelledby="invite-list-title"><h3 id="invite-list-title">Existing invites</h3>{loadingInvites ? <LoadingLine /> : invites.length ? invites.map((invite) => <div className="invite-row" key={invite.id}><div><strong>{invite.email_bound ? "Email-bound legacy invite" : "Local account invite"}</strong><p>{invite.uses_count}/{invite.max_uses} uses · expires {dateTime(invite.expires_at)}</p>{invite.email_bound && <small>This invite cannot be used for local signup. Revoke it and create a replacement.</small>}</div><div className="invite-row-actions"><StatusLabel status={invite.status} />{invite.status === "active" && <button className="button button-quiet button-small" type="button" onClick={() => { void revoke(invite); }}>Revoke</button>}</div></div>) : <p className="field-help">No invitations have been created.</p>}</section>
    </Dialog.Content></Dialog.Portal></Dialog.Root>;
}

function PeopleTable({ people, onEditPolicy, onToggle }: { people: PersonRecord[]; onEditPolicy: (person: PersonRecord) => void; onToggle: (person: PersonRecord) => void }) {
  return <div className="table-scroll"><table><thead><tr><th>Person</th><th>Status</th><th>Shared allowance</th><th>RPM</th><th>Keys</th><th>Requests</th><th>Last active</th><th>Actions</th></tr></thead><tbody>{people.map((person) => <tr key={person.id}><td><strong>{person.displayName}</strong><small>{person.email ?? "Email not provided"}</small></td><td><StatusLabel status={person.status} /></td><td><MoneyRunway label={`${person.displayName} shared allowance`} usedUsd={person.usedUsd} limitUsd={person.allowanceUsd} period={person.allowancePeriod} reservedUsd={person.reservedUsd} remainingUsd={remainingUsd(person.allowanceUsd, person.usedUsd, person.reservedUsd)} resetAt={person.allowanceResetAt} /></td><td>{count(person.rpmLimit)}</td><td>{count(person.keyCount)}</td><td>{count(person.requestCount)}</td><td>{dateTime(person.lastActiveAt)}</td><td><div className="row-actions"><button type="button" className="button button-quiet button-small" onClick={() => onEditPolicy(person)}>Limits</button><button type="button" className="button button-quiet button-small" onClick={() => { void onToggle(person); }}>{person.status === "disabled" ? "Enable" : "Disable"}</button></div></td></tr>)}</tbody></table></div>;
}

export function PersonPolicyDialog({ person, onClose, onSaved }: { person: PersonRecord | null; onClose: () => void; onSaved: () => void }) {
  const [allowance, setAllowance] = useState("");
  const [period, setPeriod] = useState<"daily" | "weekly" | "monthly">("monthly");
  const [rpm, setRpm] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    setAllowance(person?.allowanceUsd == null ? "" : String(person.allowanceUsd));
    setPeriod(person?.allowancePeriod === "daily" || person?.allowancePeriod === "monthly" ? person.allowancePeriod : "weekly");
    setRpm(person?.rpmLimit == null ? "" : String(person.rpmLimit));
    setError(null);
  }, [person]);

  async function save(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();

    if (!person) return;
    const allowanceValue = allowance.trim() || null;
    const rpmValue = rpm.trim() ? Number(rpm) : null;

    if ((allowanceValue != null && !/^(?:0|[1-9]\d*)(?:\.\d+)?$/.test(allowanceValue)) || (rpmValue != null && (!Number.isInteger(rpmValue) || rpmValue < 1))) {
      setError("Use a nonnegative decimal USD allowance and a whole-number RPM, or leave either unlimited.");

      return;
    }

    setSaving(true);
    setError(null);

    try {
      await api.updatePersonPolicy(person.id, { allowanceUsd: allowanceValue, allowancePeriod: allowanceValue == null ? null : period, rpmLimit: rpmValue });
      onSaved();
      onClose();
    } catch {
      setError("Could not save the account policy. Check that limits are stricter than any existing key limits.");
    } finally {
      setSaving(false);
    }
  }

  return <Dialog.Root open={Boolean(person)} onOpenChange={(open) => { if (!open) onClose(); }}>
    <Dialog.Portal>
      <Dialog.Overlay className="dialog-overlay" />
      <Dialog.Content className="dialog-content" aria-describedby="person-policy-description">
        <div className="dialog-title-row">
          <div>
            <Dialog.Title>Account limits</Dialog.Title>
            <Dialog.Description id="person-policy-description">{person?.displayName} · limits apply across all of this person’s keys.</Dialog.Description>
          </div>
          <Dialog.Close asChild><button className="icon-button" aria-label="Close"><X size={18} /></button></Dialog.Close>
        </div>
        <form className="dialog-form" onSubmit={save}>
          <label className="field-label" htmlFor="person-allowance">USD allowance</label>
          <input id="person-allowance" inputMode="decimal" value={allowance} onChange={(event) => setAllowance(event.target.value)} placeholder="Unlimited" />
          <label className="field-label" htmlFor="person-allowance-period">Allowance period</label>
          <select id="person-allowance-period" value={period} disabled={!allowance} onChange={(event) => {
            const value = event.target.value;

            if (value === "daily" || value === "weekly" || value === "monthly") setPeriod(value);
          }}>
            <option value="daily">Daily</option>
            <option value="weekly">Weekly</option>
            <option value="monthly">Monthly</option>
          </select>
          <label className="field-label" htmlFor="person-rpm">Requests per minute</label>
          <input id="person-rpm" type="number" min="1" step="1" value={rpm} onChange={(event) => setRpm(event.target.value)} placeholder="Unlimited" />
          <p className="field-help">Each key the person owns shares this user-wide RPM bucket.</p>
          {error && <div className="inline-notice notice-error" role="alert"><ShieldAlert size={16} /><span>{error}</span></div>}
          <div className="dialog-actions">
            <Dialog.Close asChild><button type="button" className="button button-quiet">Cancel</button></Dialog.Close>
            <button className="button button-primary" disabled={saving}>{saving ? "Saving…" : "Save limits"}</button>
          </div>
        </form>
      </Dialog.Content>
    </Dialog.Portal>
  </Dialog.Root>;
}

function ProvidersPage() {
  return <ProviderListPage portalApi={api} />;
}

function ProviderList({ providers, onSync, syncingId }: { providers: Array<ProviderRecord | import("../contracts/api").ProviderConnectionRecord>; onSync?: (providerId: string) => void; syncingId?: string | null }) {
  return <div className="provider-list">{providers.map((provider) => <div className="provider-row" key={provider.id}><span className="provider-icon"><Network size={17} /></span><div className="provider-copy"><strong>{"brandName" in provider ? `${provider.brandName} · ${provider.connectionLabel}` : provider.name}</strong><small className="mono">{provider.baseUrlDisplay}</small></div><div className="provider-model-count">{count(provider.approvedModels)} / {count(provider.discoveredModels)} models approved</div><StatusLabel status={provider.health} /><span className="provider-sync">Synced {dateTime(provider.lastSyncAt)}</span>{onSync && <button className="button button-secondary button-small" type="button" disabled={syncingId === provider.id} onClick={() => onSync(provider.id)}>{syncingId === provider.id ? "Syncing…" : "Sync models"}</button>}</div>)}</div>;
}

export function ProviderCreateDialog({ open, onOpenChange, onCreated }: { open: boolean; onOpenChange: (open: boolean) => void; onCreated: () => void }) {
  const [name, setName] = useState("");
  const [baseUrl, setBaseUrl] = useState("");
  const [apiKey, setApiKey] = useState("");
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function submit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setSaving(true);
    setError(null);

    try {
      await api.createProvider({ name: name.trim(), brandSlug: name.trim().toLowerCase().replace(/[^a-z0-9]+/g, "-"), connectionLabel: name.trim(), baseUrl: baseUrl.trim(), apiKey });
      setApiKey("");
      onOpenChange(false);
      onCreated();
    } catch (caught) {
      setError(caught instanceof ApiError ? caught.message : "Provider could not be saved.");
    } finally {
      setSaving(false);
    }
  }

  return <Dialog.Root open={open} onOpenChange={onOpenChange}>
    <Dialog.Portal><Dialog.Overlay className="dialog-overlay" /><Dialog.Content className="dialog-content" aria-describedby="provider-dialog-description">
      <div className="dialog-title-row"><div><Dialog.Title>Add a provider</Dialog.Title><Dialog.Description id="provider-dialog-description">Credentials are encrypted on the server and cannot be viewed again.</Dialog.Description></div><Dialog.Close asChild><button className="icon-button" aria-label="Close"><X size={18} /></button></Dialog.Close></div>
      <form onSubmit={submit} className="dialog-form">
        <label className="field-label" htmlFor="provider-name">Provider name</label><input id="provider-name" required maxLength={80} value={name} onChange={(event) => setName(event.target.value)} placeholder="e.g. Team inference" />
        <label className="field-label" htmlFor="provider-base-url">OpenAI-compatible base URL</label><input id="provider-base-url" type="url" required value={baseUrl} onChange={(event) => setBaseUrl(event.target.value)} placeholder="https://api.example.com/v1" />
        <label className="field-label" htmlFor="provider-api-key">Upstream API key</label><input id="provider-api-key" type="password" required autoComplete="new-password" value={apiKey} onChange={(event) => setApiKey(event.target.value)} placeholder="Entered once, never returned" />
        <p className="field-help">Use a public HTTPS endpoint. The key is sent only to this server and is never included in logs or API responses.</p>
        {error && <div className="inline-notice notice-error" role="alert"><ShieldAlert size={16} /><span>{error}</span></div>}
        <div className="dialog-actions"><Dialog.Close asChild><button type="button" className="button button-quiet">Cancel</button></Dialog.Close><button type="submit" className="button button-primary" disabled={saving}>{saving ? "Saving…" : "Save provider"}</button></div>
      </form>
    </Dialog.Content></Dialog.Portal>
  </Dialog.Root>;
}

export function ModelPolicyRow({ model, onSaved }: { model: ModelRecord; onSaved: () => void }) {
  const [inputPrice, setInputPrice] = useState(model.inputUsdPerMillion == null ? "" : String(model.inputUsdPerMillion));
  const [outputPrice, setOutputPrice] = useState(model.outputUsdPerMillion == null ? "" : String(model.outputUsdPerMillion));
  const [cachePrice, setCachePrice] = useState(model.cacheUsdPerMillion == null ? "" : String(model.cacheUsdPerMillion));
  const [priceSource, setPriceSource] = useState(model.priceSource ?? "");
  const [capabilities, setCapabilities] = useState<Array<"text" | "vision">>(model.capabilities);
  const [approved, setApproved] = useState(model.available && model.approved);
  const [saving, setSaving] = useState(false);
  const [message, setMessage] = useState<string | null>(null);

  async function savePolicy() {
    if (!model.providerId || !inputPrice.trim() || !outputPrice.trim() || !Number.isFinite(Number(inputPrice)) || !Number.isFinite(Number(outputPrice))) {
      setMessage("Enter valid input and output prices before saving.");

      return;
    }

    if (approved && !priceSource.trim()) {
      setMessage("Add the source used to verify pricing before approval.");

      return;
    }

    if (approved && !capabilities.includes("text")) {
      setMessage("This gateway serves chat completions, so an approved model must support text chat.");

      return;
    }

    setSaving(true);
    setMessage(null);

    try {
      await api.setModelPolicy(model.providerId, model.id, {
        inputUsdPerMillion: Number(inputPrice),
        outputUsdPerMillion: Number(outputPrice),
        cacheUsdPerMillion: cachePrice.trim() ? Number(cachePrice) : null,
        priceSource: priceSource.trim(),
        capabilities,
        approved,
      });
      setMessage("Model policy saved.");
      onSaved();
    } catch {
      setMessage("Model policy could not be saved. Check the prices and provider state.");
    } finally {
      setSaving(false);
    }
  }

  return <div className="model-policy-row"><div className="model-policy-heading"><strong className="mono">{model.upstreamModelId ?? model.id}</strong><span>{model.providerName} · {!model.available ? "Blocked" : model.approved ? "Approved" : "Pending review"}</span></div><div className="form-two-col model-price-fields"><label><span className="field-label">Input USD / 1M</span><input type="number" min="0" step="0.000001" value={inputPrice} onChange={(event) => setInputPrice(event.target.value)} /></label><label><span className="field-label">Output USD / 1M</span><input type="number" min="0" step="0.000001" value={outputPrice} onChange={(event) => setOutputPrice(event.target.value)} /></label><label><span className="field-label">Cached input USD / 1M</span><input type="number" min="0" step="0.000001" value={cachePrice} onChange={(event) => setCachePrice(event.target.value)} placeholder="Optional" /></label><label><span className="field-label">Pricing source</span><input value={priceSource} onChange={(event) => setPriceSource(event.target.value)} placeholder="Official provider price page" /></label></div><div className="model-policy-actions"><label className="checkbox-label"><input type="checkbox" checked={capabilities.includes("text")} onChange={(event) => setCapabilities((current) => event.target.checked ? [...current, "text"] : current.filter((capability) => capability !== "text"))} /> Text chat</label><label className="checkbox-label"><input type="checkbox" checked={capabilities.includes("vision")} onChange={(event) => setCapabilities((current) => event.target.checked ? [...current, "vision"] : current.filter((capability) => capability !== "vision"))} /> Vision input</label><label className="checkbox-label"><input type="checkbox" checked={approved} onChange={(event) => setApproved(event.target.checked)} /> Allow developers to use this model</label><button type="button" className="button button-secondary button-small" disabled={saving} onClick={() => { void savePolicy(); }}>{saving ? "Saving…" : "Save model policy"}</button>{message && <span role="status" className="field-help">{message}</span>}</div></div>;
}

export function OperatorUsagePage() {
  const activity = useLoad(() => api.listOperatorActivity());
  const [model, setModel] = useState("");
  const [status, setStatus] = useState("all");
  const rows = activity.value?.items ?? [];
  const filtered = rows.filter((row) => (!model || row.modelId.toLowerCase().includes(model.toLowerCase())) && (status === "all" || row.status === status));

  return <><PageHeader title="Usage" description="Investigate requests across users, keys, models, and provider outcomes." /><DataNotice error={activity.error} onRetry={activity.reload} /><ActivityFilters model={model} onModelChange={setModel} status={status} onStatusChange={setStatus} />{activity.loading ? <LoadingLine /> : filtered.length ? <ActivityTable rows={filtered} developer={false} /> : <EmptyState title="No usage events returned" body="Operator-level request history and client IPs will be available when the usage API is connected." />}</>;
}

function GuardrailsPage() {
  const data = useLoad(api.getGuardrails);
  const snapshot = data.value;
  const [ip, setIp] = useState("");
  const [reason, setReason] = useState("");
  const [globalCap, setGlobalCap] = useState("");
  const [safetyReserve, setSafetyReserve] = useState("");
  const [saving, setSaving] = useState(false);
  const [actionError, setActionError] = useState<string | null>(null);

  useEffect(() => {
    setGlobalCap(snapshot?.globalSpendCapUsd == null ? "" : String(snapshot.globalSpendCapUsd));
    setSafetyReserve(snapshot?.safetyReserveUsd == null ? "" : String(snapshot.safetyReserveUsd));
  }, [snapshot]);

  async function saveBudget(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const cap = Number(globalCap);
    const reserve = safetyReserve.trim() ? Number(safetyReserve) : 0;

    if (!Number.isFinite(cap) || cap <= 0 || !Number.isFinite(reserve) || reserve < 0 || reserve >= cap) {
      setActionError("Enter a positive global cap and a safety reserve below that cap.");

      return;
    }

    setSaving(true);
    setActionError(null);

    try {
      await api.updateGuardrails({ globalSpendCapUsd: cap, safetyReserveUsd: reserve });
      data.reload();
    } catch {
      setActionError("Budget guardrails could not be saved.");
    } finally {
      setSaving(false);
    }
  }

  async function toggleStop() {
    if (!snapshot) return;
    const stop = !snapshot.globalStopped;

    if (stop && !window.confirm("Stop all new gateway requests now? Active streams may finish.")) return;
    setSaving(true);
    setActionError(null);

    try {
      await api.setGlobalStop(stop);
      data.reload();
    } catch {
      setActionError("The global stop could not be updated.");
    } finally {
      setSaving(false);
    }
  }

  async function blockAddress(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setSaving(true);
    setActionError(null);

    try {
      await api.blockIp({ ip: ip.trim(), reason: reason.trim() || "Operator block" });
      setIp("");
      setReason("");
      data.reload();
    } catch {
      setActionError("Could not block that IP. Check the address and try again.");
    } finally {
      setSaving(false);
    }
  }

  async function unblockAddress(address: string) {
    setSaving(true);
    setActionError(null);

    try {
      await api.unblockIp(address);
      data.reload();
    } catch {
      setActionError("Could not remove the IP block.");
    } finally {
      setSaving(false);
    }
  }

  return <><PageHeader title="Guardrails & audit" description="Control access and investigate abuse without losing historical records." /><DataNotice error={data.error ?? actionError} onRetry={data.reload} /><div className="content-grid guardrail-grid"><section className="section-block"><div className="section-heading"><div><h2>Global hard stop</h2><p>Emergency stop and safety reserve.</p></div><ShieldAlert size={18} /></div>{data.loading ? <LoadingLine /> : snapshot ? <div className="guardrail-value"><StatusLabel status={snapshot.globalStopped ? "stopped" : "active"} /><strong>{snapshot.globalStopped ? "Requests are stopped" : "Requests are not globally stopped"}</strong><p>Spend cap: {money(snapshot.globalSpendCapUsd)} · accounted usage: {money(snapshot.globalSpendUsedUsd)} · reserve: {money(snapshot.safetyReserveUsd)}</p><button className="button button-secondary" disabled={saving} onClick={() => { void toggleStop(); }}>{snapshot.globalStopped ? "Resume gateway" : "Stop gateway"}</button><form className="guardrail-budget-form" onSubmit={saveBudget}><label><span className="field-label">Global spend cap (USD)</span><input required type="number" min="0.01" step="0.01" value={globalCap} onChange={(event) => setGlobalCap(event.target.value)} /></label><label><span className="field-label">Safety reserve (USD)</span><input required type="number" min="0" step="0.01" value={safetyReserve} onChange={(event) => setSafetyReserve(event.target.value)} /></label><button className="button button-secondary" disabled={saving}>{saving ? "Saving…" : "Save budget"}</button></form></div> : <EmptyState title="Guardrail state unavailable" body="The operator API could not confirm current stop status." compact />}</section><section className="section-block"><div className="section-heading"><div><h2>Blocked IPs</h2><p>Block a source after reviewing abuse signals.</p></div><Ban size={18} /></div><form className="ip-block-form" onSubmit={blockAddress}><label><span className="field-label">IP address</span><input required value={ip} onChange={(event) => setIp(event.target.value)} placeholder="203.0.113.24" /></label><label><span className="field-label">Reason</span><input value={reason} onChange={(event) => setReason(event.target.value)} placeholder="Observed request abuse" /></label><button className="button button-secondary" disabled={saving}>{saving ? "Saving…" : "Block IP"}</button></form>{snapshot?.blockedIps.length ? <div className="simple-list">{snapshot.blockedIps.map((entry) => <div key={`${entry.ip}:${entry.createdAt}`}><code>{entry.ip}</code><span>{entry.reason ?? "No reason recorded"}</span><button type="button" className="button button-quiet button-small" disabled={saving} onClick={() => { void unblockAddress(entry.ip); }}>Unblock</button></div>)}</div> : <EmptyState title="No blocked IPs" body="No IP blocks are currently reported." compact />}</section><section className="section-block audit-section"><div className="section-heading"><div><h2>Recent audit events</h2><p>Policy actions with secret values redacted.</p></div><LockKeyhole size={18} /></div>{snapshot?.recentAudit.length ? <div className="audit-list">{snapshot.recentAudit.map((event) => <div className="audit-row" key={event.id}><span><strong>{event.action}</strong><small>{event.actor} · {event.target}</small></span><time>{dateTime(event.occurredAt)}</time></div>)}</div> : <EmptyState title="No recent audit events" body="Operator changes will be recorded here." compact />}</section></div></>;
}

function NotFound() {
  return <section className="section-block"><PageHeader title="Page not found" description="That page isn’t part of this portal." /><NavLink className="button button-secondary" to="/developer">Go to developer home <ArrowRight size={15} /></NavLink></section>;
}
