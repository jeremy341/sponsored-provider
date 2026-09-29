import { useState } from "react";
import { Link2Off, Plus, Ticket } from "lucide-react";
import { api } from "../../lib/api";
import type { CreateInviteResult, InviteRecord } from "../../contracts/api";
import { count, dateTime } from "../../lib/format";
import { ConfirmDialog } from "../ConfirmDialog";
import { DataNotice, EmptyState, LoadingLine, PageHeader, StatusLabel, useLoad } from "../shared";
import { SelectMenu } from "../SelectMenu";

const ALL = "__all__";

/** Operator invites: single-use links with expiry, email binding optional.
 * Raw tokens are shown once at creation and stored only as hashes. */
export function InvitesPage() {
  const load = useLoad(() => api.listOperatorInvites(), []);
  const [creating, setCreating] = useState(false);
  const [expiresIn] = useState("604800");
  const [created, setCreated] = useState<CreateInviteResult | null>(null);
  const [createError, setCreateError] = useState<string | null>(null);
  const [copied, setCopied] = useState(false);
  const [revokeTarget, setRevokeTarget] = useState<InviteRecord | null>(null);
  const [revoking, setRevoking] = useState(false);
  const [statusFilter, setStatusFilter] = useState(ALL);

  const invites = (load.value ?? []).filter((invite) => statusFilter === ALL || invite.status === statusFilter);

  async function createInvite() {
    setCreating(true);
    setCreateError(null);
    try {
      const result = await api.createInvite({ max_uses: 1, expires_in_seconds: Number(expiresIn) });
      setCreated(result);
      load.reload();
    } catch {
      setCreateError("The invite could not be created. Retry or check the server logs.");
    } finally {
      setCreating(false);
    }
  }

  async function revokeInvite() {
    if (!revokeTarget) return;
    setRevoking(true);
    try {
      await api.revokeInvite(revokeTarget.id);
      setRevokeTarget(null);
      load.reload();
    } catch {
      setRevokeTarget(null);
      load.reload();
    } finally {
      setRevoking(false);
    }
  }

  const inviteUrl = created ? `${window.location.origin}/auth/login#invite=${created.invite_token}` : null;

  return <section className="page invites-page" aria-label="Invites">
    <PageHeader
      title="Invites"
      description="Signup is invite-only. Each invitation is single-use, expires, and is stored as a hash — the raw link is shown once."
      action={<button type="button" className="button button-primary" onClick={() => void createInvite()} disabled={creating}><Plus size={15} />{creating ? "Creating…" : "New invite"}</button>}
    />
    {createError && <DataNotice error={createError} />}
    {created && inviteUrl && <div className="created-key-state" role="status">
      <p className="inline-notice notice-success">Invitation created. The link is shown only now; save it before leaving this page.</p>
      <label className="field-label" htmlFor="created-invite-link">Invitation link</label>
      <div className="secret-field">
        <input id="created-invite-link" className="mono" readOnly value={inviteUrl} />
        <button type="button" className="button button-secondary" onClick={() => {
          void navigator.clipboard.writeText(inviteUrl).then(() => { setCopied(true); window.setTimeout(() => setCopied(false), 1500); }).catch(() => undefined);
        }}>{copied ? "Copied" : "Copy"}</button>
      </div>
    </div>}
    <div className="logs-filter-bar" role="group" aria-label="Invite filters">
      <Ticket size={15} aria-hidden="true" />
      <SelectMenu
        ariaLabel="Filter by status"
        value={statusFilter}
        onValueChange={setStatusFilter}
        options={[
          { value: ALL, label: "All statuses" },
          { value: "active", label: "Active" },
          { value: "exhausted", label: "Exhausted" },
          { value: "expired", label: "Expired" },
          { value: "revoked", label: "Revoked" },
        ]}
      />
    </div>
    {load.loading ? <LoadingLine /> : invites.length === 0
      ? <EmptyState title="No invitations" body="No invitations match this filter. Create one to add a developer." developer />
      : <div className="table-scroll" tabIndex={0} role="region" aria-label="Invitations">
          <table>
            <thead><tr><th scope="col">Created</th><th scope="col">Status</th><th scope="col">Email binding</th><th scope="col" className="numeric">Uses</th><th scope="col">Expires</th><th scope="col">Actions</th></tr></thead>
            <tbody>
              {invites.map((invite) => <tr key={invite.id}>
                <td className="mono">{dateTime(invite.created_at)}</td>
                <td><StatusLabel status={invite.status} /></td>
                <td>{invite.bound_email ? <span className="mono">{invite.bound_email}</span> : "Any email"}</td>
                <td className="numeric mono">{count(invite.uses_count)}/{count(invite.max_uses)}</td>
                <td className="mono">{dateTime(invite.expires_at)}</td>
                <td>{invite.status === "active"
                  ? <button type="button" className="button button-small button-ghost" onClick={() => setRevokeTarget(invite)}><Link2Off size={14} />Revoke</button>
                  : <span className="muted">—</span>}</td>
              </tr>)}
            </tbody>
          </table>
        </div>}
    <ConfirmDialog
      request={revokeTarget ? {
        title: "Revoke this invitation?",
        body: `The link created ${dateTime(revokeTarget.created_at)} stops working immediately. This cannot be undone.`,
        confirmLabel: "Revoke invite",
        destructive: true,
      } : null}
      busy={revoking}
      onCancel={() => setRevokeTarget(null)}
      onConfirm={() => void revokeInvite()}
    />
  </section>;
}
