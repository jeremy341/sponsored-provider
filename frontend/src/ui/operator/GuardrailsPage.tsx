import { useEffect, useState } from "react";
import { Ban, Globe2, Landmark, ScrollText, ShieldAlert, ShieldX } from "lucide-react";
import { api } from "../../lib/api";
import { dateTime, money } from "../../lib/format";
import { DataNotice, EmptyState, LoadingLine, PageHeader, StatusLabel, useLoad } from "../shared";
import { ConfirmDialog } from "../ConfirmDialog";

const IPV4 = /^(25[0-5]|2[0-4]\d|1\d\d|[1-9]?\d)(\.(25[0-5]|2[0-4]\d|1\d\d|[1-9]?\d)){3}$/;

function isValidAddress(value: string): boolean {
  if (IPV4.test(value)) return true;

  // Rough IPv6 shape check; the server remains authoritative via ipaddress.ip_address().
  return value.includes(":") && /^[0-9a-fA-F:]+$/.test(value) && value.split(":").length >= 3 && value.length <= 45;
}

export function GuardrailsPage() {
  const data = useLoad(api.getGuardrails);
  const snapshot = data.value;
  const [ip, setIp] = useState("");
  const [reason, setReason] = useState("");
  const [globalCap, setGlobalCap] = useState("");
  const [safetyReserve, setSafetyReserve] = useState("");
  const [budgetSaving, setBudgetSaving] = useState(false);
  const [ipSaving, setIpSaving] = useState(false);
  const [actionError, setActionError] = useState<string | null>(null);
  const [confirmStop, setConfirmStop] = useState(false);
  const [stopBusy, setStopBusy] = useState(false);

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

    setBudgetSaving(true);
    setActionError(null);

    try {
      await api.updateGuardrails({ globalSpendCapUsd: cap, safetyReserveUsd: reserve });
      data.reload();
    } catch {
      setActionError("Budget guardrails could not be saved.");
    } finally {
      setBudgetSaving(false);
    }
  }

  function requestStop() {
    if (!snapshot || stopBusy) return;

    if (snapshot.globalStopped) {
      void runStop(true);

      return;
    }

    setConfirmStop(true);
  }

  async function runStop(resume: boolean) {
    if (!snapshot) return;

    setStopBusy(true);
    setActionError(null);

    try {
      await api.setGlobalStop(resume ? false : true);
      data.reload();
      setConfirmStop(false);
    } catch {
      setActionError("The global stop could not be updated.");
    } finally {
      setStopBusy(false);
    }
  }

  async function blockAddress(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();

    if (!isValidAddress(ip.trim())) {
      setActionError("Enter a valid IPv4 or IPv6 address, for example 203.0.113.24.");

      return;
    }

    setIpSaving(true);
    setActionError(null);

    try {
      await api.blockIp({ ip: ip.trim(), reason: reason.trim() || "Operator block" });
      setIp("");
      setReason("");
      data.reload();
    } catch {
      setActionError("Could not block that IP. Check the address and try again.");
    } finally {
      setIpSaving(false);
    }
  }

  async function unblockAddress(address: string) {
    setIpSaving(true);
    setActionError(null);

    try {
      await api.unblockIp(address);
      data.reload();
    } catch {
      setActionError("Could not remove the IP block.");
    } finally {
      setIpSaving(false);
    }
  }

  const stopped = snapshot?.globalStopped ?? false;

  return <>
    <PageHeader title="Guardrails & audit" description="Control access and investigate abuse without losing historical records." />
    <DataNotice error={data.error} onRetry={data.reload} />
    {actionError && <div className="inline-notice notice-error" role="alert"><ShieldAlert size={16} /><span>{actionError}</span></div>}

    <section className="section-block guardrail-gateway" aria-labelledby="gateway-heading">
      <div className="section-heading"><div><h2 id="gateway-heading">Global gateway</h2><p>Live status of the request path and the shared budget it draws on.</p></div><Globe2 size={18} /></div>
      {data.loading ? <LoadingLine /> : snapshot ? <div className="gateway-state">
        <div className="gateway-status">
          <StatusLabel status={stopped ? "stopped" : "active"} />
          <strong>{stopped ? "Requests are stopped" : "Requests are being served"}</strong>
          <p>Spend cap {money(snapshot.globalSpendCapUsd)} · accounted usage {money(snapshot.globalSpendUsedUsd)} · safety reserve {money(snapshot.safetyReserveUsd)}</p>
        </div>
        <div className="gateway-stop">
          <button type="button" className={stopped ? "button button-secondary guardrail-resume-button" : "button guardrail-stop-button"} disabled={stopBusy} onClick={requestStop}>
            <ShieldX size={15} aria-hidden="true" />{stopped ? "Resume gateway" : "Stop gateway"}
          </button>
          <p className="field-help">{stopped ? "Resuming lets new requests through again." : "Stopping rejects every new gateway request until you resume."}</p>
        </div>
      </div> : <EmptyState title="Guardrail state unavailable" body="The operator API could not confirm current stop status." compact />}
    </section>

    <div className="content-grid guardrail-grid">
      <section className="section-block" aria-labelledby="budget-heading">
        <div className="section-heading"><div><h2 id="budget-heading">Budget limits</h2><p>The cap and reserve applied to every gateway estimate.</p></div><Landmark size={18} /></div>
        <form className="guardrail-budget-form" onSubmit={saveBudget}>
          <label><span className="field-label">Global spend cap (USD)</span><input required type="number" min="0.01" step="0.01" value={globalCap} onChange={(event) => setGlobalCap(event.target.value)} /></label>
          <label><span className="field-label">Safety reserve (USD)</span><input required type="number" min="0" step="0.01" value={safetyReserve} onChange={(event) => setSafetyReserve(event.target.value)} /></label>
          <button className="button button-secondary" disabled={budgetSaving}>{budgetSaving ? "Saving…" : "Save budget"}</button>
        </form>
      </section>

      <section className="section-block" aria-labelledby="blocked-heading">
        <div className="section-heading"><div><h2 id="blocked-heading">Blocked sources</h2><p>Block a source after reviewing abuse signals.</p></div><Ban size={18} /></div>
        <form className="ip-block-form" onSubmit={blockAddress}>
          <label><span className="field-label">IP address</span><input required value={ip} onChange={(event) => setIp(event.target.value)} placeholder="203.0.113.24" autoComplete="off" spellCheck={false} /></label>
          <label><span className="field-label">Reason</span><input value={reason} onChange={(event) => setReason(event.target.value)} placeholder="Observed request abuse" /></label>
          <button className="button button-secondary" disabled={ipSaving}>{ipSaving ? "Saving…" : "Block IP"}</button>
        </form>
        {snapshot?.blockedIps.length ? <div className="simple-list">{snapshot.blockedIps.map((entry) => <div key={`${entry.ip}:${entry.createdAt}`}><code>{entry.ip}</code><span>{entry.reason ?? "No reason recorded"} · blocked {dateTime(entry.createdAt)}</span><button type="button" className="button button-quiet button-small" disabled={ipSaving} onClick={() => { void unblockAddress(entry.ip); }}>Unblock</button></div>)}</div> : <EmptyState title="No blocked IPs" body="No IP blocks are currently reported." compact />}
      </section>

      <section className="section-block audit-section" aria-labelledby="audit-heading">
        <div className="section-heading"><div><h2 id="audit-heading">Recent audit events</h2><p>Policy actions with secret values redacted.</p></div><ScrollText size={18} /></div>
        {snapshot?.recentAudit.length ? <div className="audit-list">{snapshot.recentAudit.map((event) => <div className="audit-row" key={event.id}><span><strong>{event.action}</strong><small>{event.actor} · {event.target}</small></span><time>{dateTime(event.occurredAt)}</time></div>)}</div> : <EmptyState title="No recent audit events" body="Operator changes will be recorded here." compact />}
      </section>
    </div>

    <ConfirmDialog request={confirmStop ? { title: "Stop all new gateway requests now?", body: "Active streams may finish.", confirmLabel: "Stop gateway", destructive: true } : null} busy={stopBusy} onCancel={() => setConfirmStop(false)} onConfirm={() => { void runStop(false); }} />
  </>;
}
