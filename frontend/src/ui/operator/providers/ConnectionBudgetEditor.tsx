import { useState } from "react";
import * as Dialog from "@radix-ui/react-dialog";
import { PixelIcon } from "../../icons/PixelIcon";
import type { PortalApi, ProviderConnectionRecord } from "../../../contracts/api";
import { formatUsd } from "../../../lib/money";

export function ConnectionBudgetEditor({ connection, portalApi, onSaved }: { connection: ProviderConnectionRecord; portalApi: PortalApi; onSaved: () => void }) {
  const [open, setOpen] = useState(false);
  const [limitUsd, setLimitUsd] = useState(connection.budget.limitUsd ?? "");
  const [period, setPeriod] = useState(connection.budget.period ?? "weekly");
  const [reserveUsd, setReserveUsd] = useState(connection.budget.reserveUsd);
  const [error, setError] = useState("");
  const [saving, setSaving] = useState(false);

  function openEditor() {
    setLimitUsd(connection.budget.limitUsd ?? "");
    setPeriod(connection.budget.period ?? "weekly");
    setReserveUsd(connection.budget.reserveUsd);
    setError("");
    setOpen(true);
  }

  async function submit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const validDecimal = (value: string) => /^(?:0|[1-9]\d*)(?:\.\d+)?$/.test(value);

    if ((limitUsd && !validDecimal(limitUsd)) || !validDecimal(reserveUsd)) {
      setError("Enter nonnegative USD values using decimal notation.");

      return;
    }

    setSaving(true);
    setError("");

    try {
      await portalApi.updateConnectionBudget(connection.id, { limitUsd: limitUsd || null, period: limitUsd ? period : null, reserveUsd });
      onSaved();
      setOpen(false);
    } catch {
      setError("Connection budget could not be saved. Check the amount and try again.");
    } finally {
      setSaving(false);
    }
  }

  return <Dialog.Root open={open} onOpenChange={setOpen}>
    <Dialog.Trigger asChild><button type="button" className="button button-quiet button-small" aria-label={`Edit cap for ${connection.connectionLabel}`} onClick={openEditor}>Edit cap</button></Dialog.Trigger>
    <Dialog.Portal><Dialog.Overlay className="dialog-overlay" /><Dialog.Content className="dialog-content" aria-describedby="connection-budget-description">
      <div className="dialog-title-row"><div><Dialog.Title>Connection budget</Dialog.Title><Dialog.Description id="connection-budget-description">{connection.brandName} · {connection.connectionLabel}. This cap controls upstream exposure for this connection.</Dialog.Description></div><Dialog.Close asChild><button type="button" className="icon-button" aria-label="Close connection budget"><PixelIcon name="close" /></button></Dialog.Close></div>
      <div className="allowance-runway-summary"><div><span>Used</span><strong>{formatUsd(connection.budget.usedUsd)}</strong></div><div><span>Reserved</span><strong>{formatUsd(connection.budget.reservedUsd)}</strong></div><div><span>Remaining</span><strong>{formatUsd(connection.budget.remainingUsd)}</strong></div><div><span>Reset</span><strong>{connection.budget.resetAt ? new Intl.DateTimeFormat("en-GB", { dateStyle: "full", timeZone: "Europe/Berlin" }).format(new Date(connection.budget.resetAt)) + " · Berlin" : "Not scheduled"}</strong></div></div>
      <form className="dialog-form" onSubmit={(event) => { void submit(event); }}>
        <label><span className="field-label">Connection cap USD</span><input aria-label="Connection cap USD" inputMode="decimal" value={limitUsd} onChange={(event) => setLimitUsd(event.target.value)} placeholder="Unlimited" /></label>
        <label><span className="field-label">Cap period</span><select aria-label="Cap period" value={period} disabled={!limitUsd} onChange={(event) => setPeriod(event.currentTarget.value)}><option value="daily">Daily</option><option value="weekly">Weekly</option><option value="monthly">Monthly</option><option value="lifetime">Lifetime</option></select></label>
        <label><span className="field-label">Safety reserve USD</span><input aria-label="Safety reserve USD" inputMode="decimal" value={reserveUsd} onChange={(event) => setReserveUsd(event.target.value)} /></label>
        <p className="field-help"><PixelIcon name="usage" /> Used, active reservations, reserve, and remaining headroom are separate values.</p>
        {error && <p className="inline-notice notice-error" role="alert">{error}</p>}
        <div className="dialog-actions"><Dialog.Close asChild><button type="button" className="button button-quiet">Cancel</button></Dialog.Close><button type="submit" className="button button-primary" disabled={saving}>{saving ? "Saving…" : "Save connection budget"}</button></div>
      </form>
    </Dialog.Content></Dialog.Portal>
  </Dialog.Root>;
}
