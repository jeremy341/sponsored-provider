import { useEffect, useState } from "react";
import { api } from "../../lib/api";
import { money } from "../../lib/format";
import { formatUsd } from "../../lib/money";
import { getLayoutPreviewRole } from "../../lib/preview";

type PillRole = "developer" | "operator";

function dotClass(ratio: number | null): string {
  if (ratio == null) return "spend-dot";

  if (ratio >= 0.9) return "spend-dot is-critical";

  if (ratio >= 0.6) return "spend-dot is-warning";

  return "spend-dot";
}

function periodWord(period: string | null): string | null {
  if (period === "day" || period === "daily") return "TODAY";

  if (period === "week" || period === "weekly") return "THIS WEEK";

  if (period === "month" || period === "monthly") return "THIS MONTH";

  return null;
}

export function AllowancePill({ role }: { role: PillRole }) {
  const [text, setText] = useState("···");
  const [period, setPeriod] = useState<string | null>(null);
  const [ratio, setRatio] = useState<number | null>(null);
  const [label, setLabel] = useState("Loading allowance");

  useEffect(() => {
    if (getLayoutPreviewRole()) {
      setText("···");
      setPeriod("PREVIEW");
      setRatio(null);
      setLabel("Allowance is not connected in layout preview");

      return;
    }

    let active = true;

    if (role === "operator") {
      api.getOperatorDashboard("current_month").then((dashboard) => {
        if (!active) return;

        const guards = dashboard.guardrails;

        if (guards?.globalSpendCapUsd == null || guards?.globalSpendUsedUsd == null) {
          setText("Not reported");
          setPeriod(null);
          setRatio(null);
          setLabel("Global spend is not reported");

          return;
        }

        const used = guards.globalSpendUsedUsd;
        const cap = guards.globalSpendCapUsd;

        setText(`${money(used)} / ${money(cap)}`);
        setPeriod("GLOBAL CAP");
        setRatio(cap > 0 ? used / cap : null);
        setLabel(`Global spend ${money(used)} of ${money(cap)} cap`);
      }).catch(() => {
        if (!active) return;

        setText("···");
        setLabel("Allowance is unavailable");
      });
    } else {
      api.getDeveloperDashboard("current_month").then((dashboard) => {
        if (!active) return;

        const allowance = dashboard.allowance;

        if (!allowance) {
          setText("Not reported");
          setPeriod(null);
          setRatio(null);
          setLabel("Allowance is not reported");

          return;
        }

        const used = Number.parseFloat(allowance.consumedUsd);
        const limit = allowance.limitUsd == null ? null : Number.parseFloat(allowance.limitUsd);

        if (!Number.isFinite(used)) {
          setText("Not reported");
          setPeriod(null);
          setRatio(null);
          setLabel("Allowance is not reported");

          return;
        }

        setText(limit == null || !Number.isFinite(limit) ? `${formatUsd(allowance.consumedUsd)} spent` : `${formatUsd(allowance.consumedUsd)} / ${formatUsd(allowance.limitUsd ?? "0")}`);
        setPeriod(periodWord(allowance.period));
        setRatio(limit == null || limit <= 0 ? null : used / limit);
        setLabel(limit == null ? `Allowance spent ${formatUsd(allowance.consumedUsd)}, no cap` : `Allowance spent ${formatUsd(allowance.consumedUsd)} of ${formatUsd(allowance.limitUsd ?? "0")}`);
      }).catch(() => {
        if (!active) return;

        setText("···");
        setLabel("Allowance is unavailable");
      });
    }

    return () => { active = false; };
  }, [role]);

  return <span className="allowance-pill" role="status" aria-label={label} title={label}>
    <span className={dotClass(ratio)} aria-hidden="true" />
    <strong>{text}</strong>
    {period ? <span className="allowance-pill-period">{period}</span> : null}
  </span>;
}
