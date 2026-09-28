import { useEffect, useState } from "react";
import * as Dialog from "@radix-ui/react-dialog";
import { X } from "lucide-react";
import type { PersonRecord } from "../../../contracts/api";
import { MoneyRunway } from "../MoneyRunway";
import { SelectMenu } from "../../SelectMenu";

export function AllowanceEditor({ person, onSave, onClose }: { person: PersonRecord; onSave: (input: { allowanceUsd: string | null; allowancePeriod: "daily" | "weekly" | "monthly" | null; rpmLimit: number | null }) => Promise<void>; onClose?: () => void }) {
  const [allowance, setAllowance] = useState(person.allowanceUsd ?? "");
  const [period, setPeriod] = useState<"daily" | "weekly" | "monthly">(person.allowancePeriod ?? "monthly");
  const [rpm, setRpm] = useState(person.rpmLimit == null ? "" : String(person.rpmLimit));
  const [error, setError] = useState(""); const [saving, setSaving] = useState(false);
  useEffect(() => { setAllowance(person.allowanceUsd ?? ""); setPeriod(person.allowancePeriod ?? "monthly"); setRpm(person.rpmLimit == null ? "" : String(person.rpmLimit)); }, [person]);

  async function submit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();

    if (allowance && !/^(?:0|[1-9]\d*)(?:\.\d+)?$/.test(allowance)) { setError("Enter a nonnegative decimal USD allowance.");

 return; }

    const rpmValue = rpm ? Number(rpm) : null;

    if (rpmValue != null && (!Number.isInteger(rpmValue) || rpmValue < 1)) { setError("RPM must be a positive whole number.");

 return; }

    setSaving(true); setError("");

    try { await onSave({ allowanceUsd: allowance || null, allowancePeriod: allowance ? period : null, rpmLimit: rpmValue }); onClose?.(); }
    catch { setError("Allowance could not be saved. Review the amount and try again."); }
    finally { setSaving(false); }
  }

  return <form className="dialog-form allowance-editor" onSubmit={(event) => { void submit(event); }}>
    <MoneyRunway label={`${person.displayName} shared allowance`} usedUsd={person.usedUsd} limitUsd={person.allowanceUsd} period={person.allowancePeriod} reservedUsd={person.reservedUsd} resetAt={person.allowanceResetAt} />
    <p className="field-help">This allowance is shared across all of {person.displayName}’s keys. Unused credits expire when the period resets.</p>
    <label><span className="field-label">USD allowance</span><input aria-label="USD allowance" inputMode="decimal" value={allowance} onChange={(event) => setAllowance(event.target.value)} placeholder="Unlimited" /></label>
    <div><span className="field-label" id="allowance-period-label">Allowance period</span><SelectMenu ariaLabel="Allowance period" value={period} disabled={!allowance} onValueChange={(value) => { if (value === "daily" || value === "weekly" || value === "monthly") setPeriod(value); }} options={[{ value: "daily", label: "Daily" }, { value: "weekly", label: "Weekly" }, { value: "monthly", label: "Monthly" }]} /></div>
    <label><span className="field-label">Requests per minute</span><input inputMode="numeric" value={rpm} onChange={(event) => setRpm(event.target.value)} placeholder="Unlimited" /></label>
    {error && <p className="inline-notice notice-error" role="alert">{error}</p>}<div className="dialog-actions"><button className="button button-primary" disabled={saving}>{saving ? "Saving…" : "Save allowance"}</button></div>
  </form>;
}

export function AllowanceDialog({ person, onSave, onClose }: { person: PersonRecord | null; onSave: AllowanceEditorProps["onSave"]; onClose: () => void }) {
  return <Dialog.Root open={Boolean(person)} onOpenChange={(open) => { if (!open) onClose(); }}><Dialog.Portal><Dialog.Overlay className="dialog-overlay" /><Dialog.Content className="dialog-content" aria-describedby="allowance-description"><div className="dialog-title-row"><div><Dialog.Title>Edit allowance</Dialog.Title><Dialog.Description id="allowance-description">Allowance applies across this person’s keys.</Dialog.Description></div><Dialog.Close asChild><button className="icon-button" aria-label="Close allowance editor"><X size={18} /></button></Dialog.Close></div>{person && <AllowanceEditor key={person.id} person={person} onSave={onSave} onClose={onClose} />}</Dialog.Content></Dialog.Portal></Dialog.Root>;
}

type AllowanceEditorProps = React.ComponentProps<typeof AllowanceEditor>;
