import { useEffect, useState } from "react";
import { api } from "../../lib/api";
import { DataNotice, LoadingLine, PageHeader } from "../shared";
import { SelectMenu } from "../SelectMenu";

type SettingsTab = "account" | "appearance" | "alerts" | "privacy" | "developer";

const TABS: Array<{ id: SettingsTab; label: string }> = [
  { id: "account", label: "Account" },
  { id: "appearance", label: "Appearance" },
  { id: "alerts", label: "Usage Alerts" },
  { id: "privacy", label: "Privacy" },
  { id: "developer", label: "Developer" },
];

const ACCENTS = [
  { id: "violet", label: "Violet", swatch: "#8B7CFF" },
  { id: "cyan", label: "Cyan", swatch: "#62C8FF" },
  { id: "green", label: "Green", swatch: "#75D79A" },
  { id: "magenta", label: "Magenta", swatch: "#D990E8" },
] as const;

const DENSITY = [
  { id: "comfortable", label: "Comfortable" },
  { id: "compact", label: "Compact" },
] as const;

const ALERT_STORE = "provider.alertThreshold";
const ACCENT_STORE = "provider.accent";
const DENSITY_STORE = "provider.density";

interface SessionInfo {
  displayName: string;
  email: string | null;
  role: "developer" | "operator";
}

/** Real settings only: appearance preferences and alert thresholds persist
 * locally; account facts come from the session; everything the portal does not
 * support yet is simply not shown. */
export function SettingsPage() {
  const [tab, setTab] = useState<SettingsTab>("account");
  const [session, setSession] = useState<SessionInfo | null>(null);
  const [sessionError, setSessionError] = useState<string | null>(null);
  const [accent, setAccent] = useState<string>(() => localStorage.getItem(ACCENT_STORE) ?? "violet");
  const [density, setDensity] = useState<string>(() => localStorage.getItem(DENSITY_STORE) ?? "comfortable");
  const [alertThreshold, setAlertThreshold] = useState<number>(() => Number(localStorage.getItem(ALERT_STORE) ?? "75"));

  useEffect(() => {
    api.getSession()
      .then((value) => setSession({ displayName: value.user.displayName, email: value.user.email, role: value.role }))
      .catch(() => setSessionError("Account details could not be loaded from the session."));
  }, []);

  useEffect(() => {
    localStorage.setItem(ACCENT_STORE, accent);
    document.documentElement.dataset.accent = accent;
  }, [accent]);

  useEffect(() => {
    localStorage.setItem(DENSITY_STORE, density);
    document.documentElement.dataset.density = density;
  }, [density]);

  useEffect(() => {
    localStorage.setItem(ALERT_STORE, String(alertThreshold));
  }, [alertThreshold]);

  return <section className="page settings-page" aria-label="Settings">
    <PageHeader title="Settings" description="Preferences for this console. Account facts come from your signed-in session." />
    <DataNotice error={sessionError} />
    <div className="settings-layout">
      <nav className="settings-nav" aria-label="Settings sections">
        {TABS.map((entry) => <button
          key={entry.id}
          type="button"
          className={tab === entry.id ? "is-active" : undefined}
          aria-current={tab === entry.id ? "page" : undefined}
          onClick={() => setTab(entry.id)}
        >{entry.label}</button>)}
      </nav>
      <div className="settings-body">
        {tab === "account" && <article className="section-block">
          <div className="section-heading"><div><h2>Account</h2><p>Signed-in identity. Contact the operator for changes.</p></div></div>
          {session == null && !sessionError ? <LoadingLine /> : session && <dl className="inspector-list">
            <div><dt>Name</dt><dd>{session.displayName}</dd></div>
            <div><dt>Email</dt><dd>{session.email ?? "Not recorded"}</dd></div>
            <div><dt>Role</dt><dd>{session.role === "operator" ? "Operator" : "Developer"}</dd></div>
          </dl>}
        </article>}
        {tab === "appearance" && <article className="section-block">
          <div className="section-heading"><div><h2>Appearance</h2><p>The console ships dark-first. Accent and density apply immediately and persist on this device.</p></div></div>
          <div className="settings-field">
            <span className="field-label">Accent</span>
            <div className="accent-row" role="radiogroup" aria-label="Accent color">
              {ACCENTS.map((option) => <button
                key={option.id}
                type="button"
                role="radio"
                aria-checked={accent === option.id}
                className={`accent-swatch${accent === option.id ? " is-active" : ""}`}
                onClick={() => setAccent(option.id)}
              ><span style={{ background: option.swatch }} aria-hidden="true" />{option.label}</button>)}
            </div>
          </div>
          <div className="settings-field">
            <span className="field-label">Density</span>
            <SelectMenu
              ariaLabel="Density"
              value={density}
              onValueChange={setDensity}
              options={DENSITY.map((option) => ({ value: option.id, label: option.label }))}
            />
          </div>
        </article>}
        {tab === "alerts" && <article className="section-block">
          <div className="section-heading"><div><h2>Usage Alerts</h2><p>Warn on this Overview when your allowance usage crosses the threshold. Stored on this device.</p></div></div>
          <div className="settings-field">
            <label className="field-label" htmlFor="alert-threshold">Alert threshold <output>{alertThreshold}%</output></label>
            <input id="alert-threshold" type="range" min={50} max={95} step={5} value={alertThreshold} onChange={(event) => setAlertThreshold(Number(event.target.value))} />
          </div>
        </article>}
        {tab === "privacy" && <article className="section-block">
          <div className="section-heading"><div><h2>Privacy</h2><p>What the gateway records about your traffic.</p></div></div>
          <p>The gateway records request <strong>metadata only</strong>: model, token counts, cost estimate, latency, status, and client IP for abuse controls. Prompts, message content, completions, and tool payloads are <strong>never persisted</strong>.</p>
          <p className="small muted">API key secrets are shown once at creation and stored only as hashes. Provider credentials are encrypted at rest and never returned by the API.</p>
        </article>}
        {tab === "developer" && <article className="section-block">
          <div className="section-heading"><div><h2>Developer</h2><p>Connect your application to the sponsored gateway.</p></div></div>
          <dl className="inspector-list">
            <div><dt>API base URL</dt><dd className="mono">{window.location.origin}/v1</dd></div>
            <div><dt>Authentication</dt><dd><span className="mono">Authorization: Bearer sk-…</span></dd></div>
          </dl>
          <p className="small muted">Your API keys appear under API Keys. Secrets are shown once at creation.</p>
        </article>}
      </div>
    </div>
  </section>;
}
