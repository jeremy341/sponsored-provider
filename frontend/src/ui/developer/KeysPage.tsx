import { useEffect, useState } from "react";
import * as Dialog from "@radix-ui/react-dialog";
import { BadgeCheck, Copy, Plus, ShieldAlert, X } from "lucide-react";
import { ApiError, api } from "../../lib/api";
import type { ApiKeyRecord, CreateKeyInput, CreateKeyResult } from "../../contracts/api";
import { DataNotice, EmptyState, LoadingLine, PageHeader, useLoad } from "../shared";
import { KeyTable } from "./KeyTable";
import { ConfirmDialog } from "../ConfirmDialog";
import { ModelAccessPicker } from "./ModelAccessPicker";
import { SelectMenu } from "../SelectMenu";

export function KeysPage() {
  const keys = useLoad(api.listKeys);
  const [open, setOpen] = useState(false);
  const [created, setCreated] = useState<CreateKeyResult | null>(null);
  const [editing, setEditing] = useState<ApiKeyRecord | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);
  const [confirm, setConfirm] = useState<{ action: "revoke" | "archive"; key: ApiKeyRecord } | null>(null);
  const [confirmBusy, setConfirmBusy] = useState(false);

  async function runConfirm() {
    if (!confirm) return;

    setConfirmBusy(true);
    setActionError(null);

    try {
      if (confirm.action === "revoke") await api.revokeKey(confirm.key.id);
      else await api.archiveKey(confirm.key.id);

      keys.reload();
      setConfirm(null);
    } catch {
      setActionError(confirm.action === "revoke" ? "The key could not be revoked. Try again or contact the operator." : "The key could not be archived. Try again or contact the operator.");
    } finally {
      setConfirmBusy(false);
    }
  }

  function revokeKey(key: ApiKeyRecord) {
    setConfirm({ action: "revoke", key });
  }

  function archiveKey(key: ApiKeyRecord) {
    setConfirm({ action: "archive", key });
  }

  return <>
    <PageHeader title="API keys" description="Create and manage your own access keys." action={<button className="button button-primary" onClick={() => { setCreated(null); setOpen(true); }}><Plus size={16} /> Create key</button>} />
    <DataNotice error={keys.error ?? actionError} onRetry={keys.reload} developer />
    <section className="section-block table-section"><div className="section-heading"><div><h2>Your keys</h2><p>Secrets are shown once at creation. Existing secrets cannot be viewed again.</p></div><span className="count-label">{keys.value != null ? `${keys.value.length} keys` : "— keys"}</span></div>
      {keys.loading ? <LoadingLine /> : keys.value?.length ? <KeyTable keys={keys.value} onEdit={setEditing} onRevoke={revokeKey} onArchive={archiveKey} /> : <EmptyState title="No API keys found" body="Choose Create key to issue a credential for your coding agent. You can limit approved models, spend, and RPM." developer />}
    </section>
    <CreateKeyDialog open={open} onOpenChange={setOpen} created={created} onCreated={setCreated} onSaved={keys.reload} />
    <EditKeyDialog keyRecord={editing} onClose={() => setEditing(null)} onSaved={keys.reload} />
    <ConfirmDialog request={confirm ? (confirm.action === "revoke"
      ? { title: `Revoke “${confirm.key.label}”?`, body: "Any client using this key will stop working immediately.", confirmLabel: "Revoke key", destructive: true }
      : { title: `Archive “${confirm.key.label}”?`, body: "Its usage history will be retained.", confirmLabel: "Archive key", destructive: true }) : null} busy={confirmBusy} onCancel={() => setConfirm(null)} onConfirm={() => { void runConfirm(); }} />
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

  return <Dialog.Root open={Boolean(keyRecord)} onOpenChange={(open) => { if (!open) onClose(); }}><Dialog.Portal><Dialog.Overlay className="dialog-overlay" /><Dialog.Content className="dialog-content" aria-describedby="edit-key-description"><div className="dialog-title-row"><div><Dialog.Title>Edit key policy</Dialog.Title><Dialog.Description id="edit-key-description">{keyRecord?.label} · values can only tighten the account-level allowance.</Dialog.Description></div><Dialog.Close asChild><button className="icon-button" aria-label="Close"><X size={18} /></button></Dialog.Close></div><form onSubmit={save} className="dialog-form"><ModelAccessPicker models={approvedModels} loading={models.loading} error={models.error} onRetry={models.reload} mode={mode} selectedModelIds={selectedModels} onModeChange={setMode} onSelectedChange={setSelectedModels} /><div className="form-two-col"><label><span className="field-label">Spend cap (USD)</span><input type="number" inputMode="decimal" min="0.000000001" step="any" value={spendCap} onChange={(event) => setSpendCap(event.target.value)} placeholder="Inherit allowance" /></label><div><span className="field-label">Reset period</span><SelectMenu ariaLabel="Reset period" value={spendPeriod ?? "week"} disabled={!spendCap} onValueChange={(period) => setSpendPeriod(period === "day" || period === "week" || period === "month" || period === "lifetime" ? period : "week")} options={[{ value: "day", label: "Daily" }, { value: "week", label: "Weekly" }, { value: "month", label: "Monthly" }, { value: "lifetime", label: "Lifetime" }]} /></div></div><label><span className="field-label">Requests per minute</span><input type="number" min="1" step="1" value={rpm} onChange={(event) => setRpm(event.target.value)} placeholder="Inherit user limit" /></label>{error && <div className="inline-notice notice-error" role="alert"><ShieldAlert size={16} /><span>{error}</span></div>}<div className="dialog-actions"><Dialog.Close asChild><button type="button" className="button button-quiet">Cancel</button></Dialog.Close><button className="button button-primary" disabled={saving}>{saving ? "Saving…" : "Save policy"}</button></div></form></Dialog.Content></Dialog.Portal></Dialog.Root>;
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
      setLabel("");
      setMode("all_approved");
      setSelectedModels([]);
      setSpendCap("");
      setRpm("");
      setError(null);
      setCopied(false);
      onCreated(null);
    }
  }, [open, onCreated]);

  const approvedModels = (models.value ?? []).filter((model) => model.approved && model.available && model.pricingVerified);

  async function submit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();

    if (mode === "selected" && selectedModels.length === 0) {
      setError("Choose at least one approved model, or select all approved models.");

      return;
    }

    setSaving(true);
    setError(null);

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
    } catch (caught) {
      setError(caught instanceof ApiError ? caught.message : "The key could not be created. Check your policy values and try again.");
    } finally {
      setSaving(false);
    }
  }

  async function copySecret() {
    if (!created) return;

    try {
      await navigator.clipboard.writeText(created.secret);
      setCopied(true);
    } catch {
      setError("Clipboard access failed. Select and copy the key manually.");
    }
  }

  return <Dialog.Root open={open} onOpenChange={onOpenChange}>
    <Dialog.Portal><Dialog.Overlay className="dialog-overlay" /><Dialog.Content className="dialog-content" aria-describedby="create-key-description">
      <div className="dialog-title-row"><div><Dialog.Title>{created ? "Your key is ready" : "Create API key"}</Dialog.Title><Dialog.Description id="create-key-description">{created ? "Copy this secret now. It will not be shown again." : "The server enforces your account allowance and approved model policy."}</Dialog.Description></div><Dialog.Close asChild><button className="icon-button" aria-label="Close"><X size={18} /></button></Dialog.Close></div>
      {created ? <div className="created-key-state"><div className="inline-notice notice-success"><BadgeCheck size={17} /><span>Key created. The secret is visible only in this dialog.</span></div><label className="field-label" htmlFor="created-secret">API key</label><div className="secret-field"><input id="created-secret" className="mono" readOnly value={created.secret} autoComplete="off" /><button type="button" className="button button-secondary" onClick={copySecret}><Copy size={15} />{copied ? "Copied" : "Copy"}</button></div><p className="field-help">Close this dialog when you’ve stored it securely. Never commit it to a repository.</p><div className="dialog-actions"><Dialog.Close asChild><button className="button button-primary">Done</button></Dialog.Close></div></div> : <form onSubmit={submit} className="dialog-form">
        <label className="field-label" htmlFor="key-label">Key name</label><input id="key-label" required maxLength={64} autoFocus value={label} onChange={(event) => setLabel(event.target.value)} placeholder="e.g. OpenCode laptop" />
        <ModelAccessPicker models={approvedModels} loading={models.loading} error={models.error} onRetry={models.reload} mode={mode} selectedModelIds={selectedModels} onModeChange={setMode} onSelectedChange={setSelectedModels} />
        <div className="form-two-col"><div><label className="field-label" htmlFor="spend-cap">Optional spend cap (USD)</label><input id="spend-cap" type="number" inputMode="decimal" min="0.000000001" step="any" value={spendCap} onChange={(event) => setSpendCap(event.target.value)} placeholder="Inherit account allowance" /><p className="field-help">A key cap can only tighten your account allowance. Minimum: $0.000000001.</p></div><div><span className="field-label" id="spend-period-label">Cap reset</span><SelectMenu ariaLabel="Cap reset" value={spendPeriod} disabled={!spendCap} onValueChange={setSpendPeriod} options={[{ value: "day", label: "Daily" }, { value: "week", label: "Weekly" }, { value: "month", label: "Monthly" }, { value: "lifetime", label: "Lifetime" }]} /></div></div>
        <div><label className="field-label" htmlFor="key-rpm">Optional requests per minute</label><input id="key-rpm" type="number" min="1" step="1" value={rpm} onChange={(event) => setRpm(event.target.value)} placeholder="Inherit account limit" /><p className="field-help">A per-key RPM can only be lower than your user-wide limit.</p></div>
        {error && <div className="inline-notice notice-error" role="alert"><ShieldAlert size={16} /><span>{error}</span></div>}
        <div className="dialog-actions"><Dialog.Close asChild><button type="button" className="button button-quiet">Cancel</button></Dialog.Close><button type="submit" className="button button-primary" disabled={saving}>{saving ? "Creating…" : "Create key"}</button></div>
      </form>}
    </Dialog.Content></Dialog.Portal>
  </Dialog.Root>;
}
