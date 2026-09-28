import { dateTime } from "../../lib/format";
import { formatUsd } from "../../lib/money";
import { count } from "../../lib/format";
import { StatusLabel } from "../shared";
import type { ApiKeyRecord } from "../../contracts/api";

export function KeyTable({ keys, onEdit, onRevoke, onArchive }: { keys: ApiKeyRecord[]; onEdit?: (key: ApiKeyRecord) => void; onRevoke?: (key: ApiKeyRecord) => void; onArchive?: (key: ApiKeyRecord) => void }) {
  const canManage = Boolean(onEdit || onRevoke || onArchive);

  return <div className="table-scroll" tabIndex={0} role="region" aria-label="Your API keys"><table><thead><tr><th scope="col">Key</th><th scope="col">Models</th><th scope="col">Spend used / cap</th><th scope="col">RPM</th><th scope="col">Status</th>{canManage && <th scope="col">Actions</th>}</tr></thead><tbody>{keys.map((key) => <tr key={key.id}><td><strong>{key.label}</strong><small className="mono">{key.prefix}••••</small></td><td>{key.modelAccess.mode === "all_approved" ? "All approved" : `${key.modelAccess.modelIds.length} selected`}</td><td>{formatUsd(key.spendUsedUsd)} used{key.spendCapUsd == null ? " · no key cap" : ` / ${formatUsd(key.spendCapUsd)} ${key.spendPeriod}`}<small>{key.spendResetAt ? `Resets ${dateTime(key.spendResetAt)}` : key.spendCapUsd == null ? "No key reset" : "No reset scheduled"}</small></td><td>{key.rpmLimit == null ? "Inherited" : count(key.rpmLimit)}</td><td><StatusLabel status={key.status} /></td>{canManage && <td><div className="row-actions">{onEdit && key.status === "active" && <button type="button" className="button button-quiet button-small" onClick={() => onEdit(key)}>Edit</button>}{onRevoke && key.status === "active" && <button type="button" className="button button-quiet button-small" onClick={() => onRevoke(key)}>Revoke</button>}{onArchive && key.status !== "archived" && <button type="button" className="button button-quiet button-small" onClick={() => onArchive(key)}>Archive</button>}</div></td>}</tr>)}</tbody></table></div>;
}
