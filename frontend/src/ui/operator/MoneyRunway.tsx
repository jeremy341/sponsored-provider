import { formatUsd, ratioPercent } from "../../lib/money";

export function MoneyRunway({ label, usedUsd, limitUsd, reservedUsd, remainingUsd, period, resetAt }: {
  label: string;
  usedUsd: string | null;
  limitUsd: string | null;
  reservedUsd: string;
  remainingUsd?: string | null;
  period?: string | null;
  resetAt?: string | null;
}) {
  const percent = ratioPercent(usedUsd, limitUsd);
  const reset = resetAt ? formatBerlinReset(resetAt) : null;
  const formattedLimit = formatUsd(limitUsd);
  const compactLimit = formattedLimit.endsWith(".00") ? formattedLimit.slice(0, -3) : formattedLimit;
  const limitLabel = period === "monthly" ? `${compactLimit}/month` : `${formattedLimit}${period ? ` · ${period}` : ""}`;

  return <div className="runway money-runway">
    <div className="runway-values"><span>{label} · {usedUsd == null ? "Usage not reported" : `${formatUsd(usedUsd)} used`}</span><strong>{limitUsd == null ? "No limit assigned" : limitLabel}</strong></div>
    <div className="runway-track" role="progressbar" aria-label={`${label} used`} aria-valuemin={0} aria-valuemax={100} aria-valuenow={percent ?? undefined} aria-valuetext={percent == null ? "Usage or limit not reported" : `${percent}% used`}>
      {percent != null && <span style={{ transform: `scaleX(${percent / 100})` }} />}
    </div>
    <p>{formatUsd(reservedUsd)} reserved{remainingUsd == null ? "" : ` · ${formatUsd(remainingUsd)} remaining`}{reset ? ` · resets in Europe/Berlin: ${reset}` : ""}</p>
  </div>;
}

export function formatBerlinReset(value: string): string {
  const date = new Date(value);

  if (Number.isNaN(date.getTime())) return "Reset time unavailable";

  const day = new Intl.DateTimeFormat("en-GB", { weekday: "long", day: "numeric", month: "long", year: "numeric", timeZone: "Europe/Berlin" }).format(date);
  const time = new Intl.DateTimeFormat("en-GB", { hour: "2-digit", minute: "2-digit", timeZone: "Europe/Berlin" }).format(date);

  return `${day} · ${time} Berlin time`;
}
