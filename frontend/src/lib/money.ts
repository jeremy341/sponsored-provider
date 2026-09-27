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
