export function formatUsd(value: string | null, maxFractionDigits = 9): string {
  if (value == null || !/^-?\d+(?:\.\d+)?$/.test(value)) return "Not reported";
  const negative = value.startsWith("-");
  const unsigned = negative ? value.slice(1) : value;
  const [wholeRaw, fractionRaw = ""] = unsigned.split(".");
  const whole = BigInt(wholeRaw);
  const digits = Math.max(0, Math.floor(maxFractionDigits));
  const keptFraction = fractionRaw.slice(0, digits);
  const omittedNonzero = /[1-9]/.test(fractionRaw.slice(digits));
  const fraction = keptFraction.replace(/0+$/, "");
  const displayFraction = fraction.padEnd(Math.min(2, digits), "0");
  const grouped = new Intl.NumberFormat("en-US", { maximumFractionDigits: 0 }).format(whole);
  const formatted = `${negative ? "−" : ""}$${grouped}${displayFraction ? `.${displayFraction}` : ""}`;

  if (!omittedNonzero) return formatted;

  if (whole === 0n && !/[1-9]/.test(keptFraction)) {
    const thresholdDigits = Math.max(2, digits);
    const threshold = `0.${"0".repeat(thresholdDigits - 1)}1`;

    return `<${negative ? "−" : ""}$${threshold}`;
  }

  return `${formatted}…`;
}

export function formatUsdExact(value: string | null): string {
  if (value == null) return "Not reported";

  const fractionDigits = value.split(".")[1]?.length ?? 0;

  return formatUsd(value, Math.max(2, fractionDigits));
}

export function ratioPercent(value: string | null, total: string | null): number | null {
  const decimal = /^(?:0|[1-9]\d*)(?:\.\d+)?$/;

  if (value == null || total == null || !decimal.test(value) || !decimal.test(total)) return null;

  const [valueWhole, valueFraction = ""] = value.split(".");
  const [totalWhole, totalFraction = ""] = total.split(".");
  const scale = Math.max(valueFraction.length, totalFraction.length);
  const numerator = BigInt(valueWhole + valueFraction.padEnd(scale, "0"));
  const denominator = BigInt(totalWhole + totalFraction.padEnd(scale, "0"));

  if (denominator === 0n) return null;

  const percent = numerator * 100n / denominator;

  return Number(percent > 100n ? 100n : percent);
}

export function remainingUsd(limit: string | null, used: string | null, reserved: string | null): string | null {
  const decimal = /^(?:0|[1-9]\d*)(?:\.\d+)?$/;

  if (limit == null || used == null || reserved == null || !decimal.test(limit) || !decimal.test(used) || !decimal.test(reserved)) return null;

  const values = [limit, used, reserved].map((value) => value.split("."));
  const scale = Math.max(...values.map(([, fraction = ""]) => fraction.length));
  const integers = values.map(([whole, fraction = ""]) => BigInt(whole + fraction.padEnd(scale, "0")));
  const remaining = integers[0] - integers[1] - integers[2];

  if (remaining <= 0n) return "0";

  if (scale === 0) return remaining.toString();

  const digits = remaining.toString().padStart(scale + 1, "0");
  const whole = digits.slice(0, -scale);
  const fraction = digits.slice(-scale).replace(/0+$/, "");

  return fraction ? `${whole}.${fraction}` : whole;
}
