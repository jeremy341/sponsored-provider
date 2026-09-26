export function money(value: number | null | undefined): string {
  return value == null
    ? "Not reported"
    : new Intl.NumberFormat(undefined, { style: "currency", currency: "USD", maximumFractionDigits: value < 0.01 ? 6 : 2 }).format(value);
}

export function count(value: number | null | undefined): string {
  return value == null ? "Not reported" : new Intl.NumberFormat().format(value);
}

export function tokens(value: number | null | undefined): string {
  return value == null ? "Not reported" : `${count(value)} tokens`;
}

export function dateTime(value: string | null | undefined): string {
  if (!value) return "Never";
  const date = new Date(value);

  return Number.isNaN(date.getTime()) ? "Unknown" : new Intl.DateTimeFormat(undefined, { dateStyle: "medium", timeStyle: "short" }).format(date);
}

export function pricePerMillion(value: number | null): string {
  return value == null ? "Pricing not configured" : `${money(value)} / 1M tokens`;
}
