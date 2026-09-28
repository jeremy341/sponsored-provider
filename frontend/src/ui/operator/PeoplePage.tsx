import { useEffect, useState } from "react";
import * as Dialog from "@radix-ui/react-dialog";
import { BadgeCheck, Copy, Plus, Search, ShieldAlert, X } from "lucide-react";
import { ApiError, api } from "../../lib/api";
import { count, dateTime } from "../../lib/format";
import { remainingUsd } from "../../lib/money";
import type { InviteRecord, PersonRecord } from "../../contracts/api";
import { DataNotice, EmptyState, LoadingLine, PageHeader, StatusLabel, useLoad } from "../shared";
import { MoneyRunway } from "./MoneyRunway";
import { AllowanceDialog } from "./people/AllowanceEditor";
import { ConfirmDialog } from "../ConfirmDialog";

export function PeoplePage() {
  const people = useLoad(api.listPeople);
  const [search, setSearch] = useState("");
  const [inviteOpen, setInviteOpen] = useState(false);
  const [createdInvite, setCreatedInvite] = useState<string | null>(null);
  const [policyPerson, setPolicyPerson] = useState<PersonRecord | null>(null);
  const [peopleActionError, setPeopleActionError] = useState<string | null>(null);
  const [confirmPerson, setConfirmPerson] = useState<PersonRecord | null>(null);
  const [confirmBusy, setConfirmBusy] = useState(false);
  const filtered = (people.value ?? []).filter((person) => `${person.displayName} ${person.email ?? ""}`.toLowerCase().includes(search.toLowerCase()));

  async function enablePerson(person: PersonRecord) {
    setPeopleActionError(null);

    try {
      await api.setPersonEnabled(person.id, true);
      people.reload();
    } catch {
      setPeopleActionError("The account status could not be changed.");
    }
  }

  async function runDisable() {
    if (!confirmPerson) return;

    setConfirmBusy(true);
    setPeopleActionError(null);

    try {
      await api.setPersonEnabled(confirmPerson.id, false);
      people.reload();
      setConfirmPerson(null);
    } catch {
      setPeopleActionError("The account status could not be changed.");
    } finally {
      setConfirmBusy(false);
    }
  }

  return <>
    <PageHeader title="People & keys" description="Manage invitations, account allowances, and user-owned keys." action={<button className="button button-primary" onClick={() => { setCreatedInvite(null); setInviteOpen(true); }}><Plus size={16} /> Invite person</button>} />
    <DataNotice error={people.error ?? peopleActionError} onRetry={people.reload} />
    <section className="section-block table-section">
      <div className="toolbar"><label className="search-field"><Search size={16} /><span className="sr-only">Search people</span><input value={search} onChange={(event) => setSearch(event.target.value)} placeholder="Search people" /></label><span className="count-label">{people.value != null ? `${filtered.length} ${filtered.length === 1 ? "person" : "people"}` : "— people"}</span></div>
      {people.loading ? <LoadingLine /> : filtered.length ? <PeopleTable people={filtered} onEditPolicy={setPolicyPerson} onToggle={(person) => { void (person.status === "disabled" ? enablePerson(person) : setConfirmPerson(person)); }} /> : <EmptyState title="No people returned" body="Create an invitation, then assign an allowance after the developer signs in." />}
    </section>
    <InviteDialog open={inviteOpen} onOpenChange={setInviteOpen} token={createdInvite} setToken={setCreatedInvite} />
    <AllowanceDialog person={policyPerson} onClose={() => setPolicyPerson(null)} onSave={(input) => api.updatePersonPolicy(policyPerson!.id, input).then(people.reload)} />
    <ConfirmDialog request={confirmPerson ? { title: `Disable ${confirmPerson.displayName}?`, body: "Their API keys will stop working immediately.", confirmLabel: "Disable account", destructive: true } : null} busy={confirmBusy} onCancel={() => setConfirmPerson(null)} onConfirm={() => { void runDisable(); }} />
  </>;
}

export function InviteDialog({ open, onOpenChange, token, setToken }: { open: boolean; onOpenChange: (open: boolean) => void; token: string | null; setToken: (token: string | null) => void }) {
  const [maxUses, setMaxUses] = useState("5");
  const [expiryDays, setExpiryDays] = useState("7");
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [copied, setCopied] = useState(false);
  const [invites, setInvites] = useState<InviteRecord[]>([]);
  const [loadingInvites, setLoadingInvites] = useState(false);
  const [confirmInvite, setConfirmInvite] = useState<InviteRecord | null>(null);
  const [revoking, setRevoking] = useState(false);
  const inviteUrl = token ? `${window.location.origin}/auth/login#invite=${encodeURIComponent(token)}` : "";

  useEffect(() => {
    if (!open) return;
    setLoadingInvites(true);
    api.listOperatorInvites().then((rows) => setInvites(rows as InviteRecord[])).catch(() => setError("Invitations could not be loaded.")).finally(() => setLoadingInvites(false));
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

  async function runRevoke() {
    if (!confirmInvite) return;

    setRevoking(true);
    setError(null);

    try {
      await api.revokeInvite(confirmInvite.id);
      setInvites(await api.listOperatorInvites() as InviteRecord[]);
      setConfirmInvite(null);
    } catch {
      setError("The invitation could not be revoked.");
    } finally {
      setRevoking(false);
    }
  }

  return <>
    <Dialog.Root open={open} onOpenChange={onOpenChange}>
      <Dialog.Portal><Dialog.Overlay className="dialog-overlay" /><Dialog.Content className="dialog-content invite-manager" aria-describedby="invite-dialog-description"><div className="dialog-title-row"><div><Dialog.Title>Invitations</Dialog.Title><Dialog.Description id="invite-dialog-description">Create local account links and manage existing invitations.</Dialog.Description></div><Dialog.Close asChild><button className="icon-button" aria-label="Close invitations"><X size={18} /></button></Dialog.Close></div>{token ? <div className="created-key-state"><div className="inline-notice notice-success"><BadgeCheck size={17} /><span>Invitation created. This raw link is visible only once. Copy it before closing.</span></div><label className="field-label" htmlFor="invite-link">Invitation link</label><div className="secret-field"><input id="invite-link" className="mono" readOnly value={inviteUrl} /><button type="button" className="button button-secondary" onClick={() => { void copyInvite(); }}><Copy size={15} />{copied ? "Copied" : "Copy"}</button></div><div className="dialog-actions"><button type="button" className="button button-primary" onClick={() => setToken(null)}>Create another</button><Dialog.Close asChild><button type="button" className="button button-quiet">Done</button></Dialog.Close></div></div> : <form className="dialog-form" onSubmit={(event) => { void submit(event); }}><div className="form-two-col"><div><label className="field-label" htmlFor="invite-max-uses">Maximum uses</label><input id="invite-max-uses" type="number" min="1" max="1000" step="1" required value={maxUses} onChange={(event) => setMaxUses(event.target.value)} /></div><div><label className="field-label" htmlFor="invite-expiry">Expires in (days)</label><input id="invite-expiry" type="number" min="1" max="30" step="1" required value={expiryDays} onChange={(event) => setExpiryDays(event.target.value)} /></div></div><p className="field-help">Defaults: five uses and seven days. Invite links are not bound to an email.</p>{error && <div className="inline-notice notice-error" role="alert"><ShieldAlert size={16} /><span>{error}</span></div>}<div className="dialog-actions"><Dialog.Close asChild><button type="button" className="button button-quiet">Close</button></Dialog.Close><button type="submit" className="button button-primary" disabled={saving}>{saving ? "Creating…" : "Create invite"}</button></div></form>}
        <section className="invite-list" aria-labelledby="invite-list-title"><h3 id="invite-list-title">Existing invites</h3>{loadingInvites ? <LoadingLine /> : invites.length ? invites.map((invite) => <div className="invite-row" key={invite.id}><div><strong>{invite.email_bound ? "Email-bound legacy invite" : "Local account invite"}</strong><p>{invite.uses_count}/{invite.max_uses} uses · expires {dateTime(invite.expires_at)}</p>{invite.email_bound && <small>This invite cannot be used for local signup. Revoke it and create a replacement.</small>}</div><div className="invite-row-actions"><StatusLabel status={invite.status} />{invite.status === "active" && <button className="button button-quiet button-small" type="button" onClick={() => setConfirmInvite(invite)}>Revoke</button>}</div></div>) : <p className="field-help">No invitations have been created.</p>}</section>
      </Dialog.Content></Dialog.Portal>
    </Dialog.Root>
    <ConfirmDialog request={confirmInvite ? { title: "Revoke this invitation?", body: `${confirmInvite.uses_count}/${confirmInvite.max_uses} accounts have already used it.`, confirmLabel: "Revoke invite", destructive: true } : null} busy={revoking} onCancel={() => setConfirmInvite(null)} onConfirm={() => { void runRevoke(); }} />
  </>;
}

function PeopleTable({ people, onEditPolicy, onToggle }: { people: PersonRecord[]; onEditPolicy: (person: PersonRecord) => void; onToggle: (person: PersonRecord) => void }) {
  return <div className="table-scroll" tabIndex={0} role="region" aria-label="People and allowances"><table><thead><tr><th scope="col">Person</th><th scope="col">Status</th><th scope="col">Shared allowance</th><th scope="col">RPM</th><th scope="col">Keys</th><th scope="col">Requests</th><th scope="col">Last active</th><th scope="col">Actions</th></tr></thead><tbody>{people.map((person) => <tr key={person.id}><td><strong>{person.displayName}</strong><small>{person.email ?? "Email not provided"}</small></td><td><StatusLabel status={person.status} /></td><td><MoneyRunway label={`${person.displayName} shared allowance`} usedUsd={person.usedUsd} limitUsd={person.allowanceUsd} period={person.allowancePeriod} reservedUsd={person.reservedUsd} remainingUsd={remainingUsd(person.allowanceUsd, person.usedUsd, person.reservedUsd)} resetAt={person.allowanceResetAt} /></td><td>{count(person.rpmLimit)}</td><td>{count(person.keyCount)}</td><td>{count(person.requestCount)}</td><td>{dateTime(person.lastActiveAt)}</td><td><div className="row-actions"><button type="button" className="button button-quiet button-small" onClick={() => onEditPolicy(person)}>Limits</button><button type="button" className="button button-quiet button-small" onClick={() => onToggle(person)}>{person.status === "disabled" ? "Enable" : "Disable"}</button></div></td></tr>)}</tbody></table></div>;
}
