import { ScrollText } from "lucide-react";
import { api } from "../../lib/api";
import { dateTime } from "../../lib/format";
import { DataNotice, EmptyState, LoadingLine, PageHeader, useLoad } from "../shared";

/** Operator audit trail, split out of the former combined "Guardrails & audit"
 *  page. Secrets are redacted by the backend before they are recorded. */
export function AuditLogPage() {
  const data = useLoad(api.getGuardrails, [api]);
  const snapshot = data.value;

  return <>
    <PageHeader title="Audit log" description="Operator policy actions with secret values redacted." />
    <DataNotice error={data.error} onRetry={data.reload} />
    {data.loading ? <LoadingLine /> : <section className="section-block audit-table-section" aria-labelledby="audit-table-heading">
      <div className="section-heading"><div><h2 id="audit-table-heading">Recorded actions</h2><p>The most recent operator actions reported by the server.</p></div><ScrollText size={18} /></div>
      {snapshot?.recentAudit.length ? <div className="table-scroll audit-table-wrap" tabIndex={0} role="region" aria-label="Audit events"><table>
        <thead><tr><th scope="col">Action</th><th scope="col">Actor</th><th scope="col">Target</th><th scope="col">When</th></tr></thead>
        <tbody>{snapshot.recentAudit.map((event) => <tr key={event.id}><td><strong className="mono">{event.action}</strong></td><td>{event.actor}</td><td><code>{event.target}</code></td><td>{dateTime(event.occurredAt)}</td></tr>)}</tbody>
      </table></div> : <EmptyState title="No audit events yet" body="Operator changes such as budget edits, IP blocks, and price approvals will be recorded here." compact />}
    </section>}
  </>;
}
