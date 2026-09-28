import { PixelIcon } from "../icons/PixelIcon";
import { formatUsd, ratioPercent } from "../../lib/money";

export interface DeveloperAllowance {
  usedUsd: string;
  reservedUsd: string;
  consumedUsd: string;
  limitUsd: string | null;
  remainingUsd: string | null;
  period: string | null;
  resetAt: string | null;
  source: string;
}

export function formatAllowanceReset(value: string | null): string {
  if (!value) return "Reset time unavailable";
  const date = new Date(value);

  if (Number.isNaN(date.getTime())) return "Reset time unavailable";

  const day = new Intl.DateTimeFormat("en-GB", { weekday: "long", day: "numeric", month: "long", year: "numeric", timeZone: "Europe/Berlin" }).format(date);
  const time = new Intl.DateTimeFormat("en-GB", { hour: "2-digit", minute: "2-digit", timeZone: "Europe/Berlin" }).format(date);

  return `${day} · ${time} Berlin`;
}

export function AllowanceSummary({ allowance }: { allowance: DeveloperAllowance | null }) {
  if (!allowance) return <section className="section-block allowance-summary"><div className="section-heading"><div><h2>Your allowance</h2><p>Shared across your active API keys.</p></div><PixelIcon name="usage" size={20} /></div><p className="empty-inline">Allowance has not been assigned.</p></section>;

  const progress = ratioPercent(allowance.consumedUsd, allowance.limitUsd);
  const formattedLimit = formatUsd(allowance.limitUsd);
  const compactLimit = formattedLimit.endsWith(".00") ? formattedLimit.slice(0, -3) : formattedLimit;

  const allowanceLabel = allowance.limitUsd == null
    ? "Not reported"
    : allowance.period === "monthly"
      ? `${compactLimit}/month`
      : `${formattedLimit} / ${allowance.period ?? "period unavailable"}`;

  return <section className="section-block allowance-summary" aria-labelledby="developer-allowance-title"><div className="section-heading"><div><h2 id="developer-allowance-title">Your shared allowance</h2><p>Shared across your keys · {allowance.period ?? "period unavailable"}</p></div><PixelIcon name="usage" size={20} /></div>
    <div className="allowance-plan-value"><span>{allowance.period === "monthly" ? "Personal monthly limit" : "Personal allowance"}</span><strong>{allowanceLabel}</strong></div>
    <div className="allowance-summary-values"><div><span>Used</span><strong>{formatUsd(allowance.usedUsd)}</strong></div><div><span>Reserved</span><strong>{formatUsd(allowance.reservedUsd)}</strong></div><div><span>Remaining</span><strong>{formatUsd(allowance.remainingUsd)}</strong></div><div><span>Total</span><strong>{formattedLimit}</strong></div></div>
    <div className="runway-track" role="progressbar" aria-label="Allowance consumed, including active reservations" aria-valuemin={0} aria-valuemax={100} aria-valuenow={progress ?? undefined}><span style={{ transform: `scaleX(${progress == null ? 0 : progress / 100})` }} /></div>
    <p className="allowance-reset"><PixelIcon name="calendar" /><span>Unused credits expire at reset · {formatAllowanceReset(allowance.resetAt)}</span></p>
    <p className="source-note">Cost basis: {allowance.source}. New requests are checked against your remaining balance before dispatch.</p>
  </section>;
}
