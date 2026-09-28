import type { ModelSpendRecord } from "../../contracts/api";

export interface SpendSlice {
  id: string;
  name: string;
  spendUsd: string;
  value: number;
  percent: number;
  requests: number;
}

export type SpendChartData =
  | { state: "incomplete"; reason: string }
  | { state: "empty"; totalSpendUsd: string }
  | { state: "ready"; totalSpendUsd: string; slices: SpendSlice[] };

const DECIMAL_USD = /^(?:0|[1-9]\d*)(?:\.\d+)?$/;

interface DecimalParts {
  whole: string;
  fraction: string;
}

function parseDecimal(value: string): DecimalParts | null {
  if (!DECIMAL_USD.test(value)) return null;

  const [whole, fraction = ""] = value.split(".");

  return { whole, fraction };
}

function toScaledInteger(value: DecimalParts, scale: number): bigint {
  const unit = 10n ** BigInt(scale);

  return BigInt(value.whole) * unit + BigInt(value.fraction.padEnd(scale, "0") || "0");
}

function formatScaledUsd(value: bigint, scale: number): string {
  const unit = 10n ** BigInt(scale);
  const whole = value / unit;
  const fraction = scale === 0 ? "" : (value % unit).toString().padStart(scale, "0").replace(/0+$/, "");

  return fraction ? `${whole}.${fraction}` : whole.toString();
}

export function buildSpendSlices(models: ModelSpendRecord[], knownSpendUsd: string | null): SpendChartData {
  if (knownSpendUsd == null) return { state: "incomplete", reason: "The server did not report a reconciled known-spend total." };
  const totalParts = parseDecimal(knownSpendUsd);

  if (totalParts == null) return { state: "incomplete", reason: "The spend total is not a valid exact USD value." };
  const parsed = models.map((model) => ({ model, parts: model.spendUsd == null ? null : parseDecimal(model.spendUsd) }));

  if (parsed.some(({ model, parts }) => model.spendUsd != null && parts == null)) return { state: "incomplete", reason: "A model spend value could not be represented exactly." };

  const scale = Math.max(totalParts.fraction.length, ...parsed.map(({ parts }) => parts?.fraction.length ?? 0));
  const total = toScaledInteger(totalParts, scale);
  const exactRows = parsed.map(({ model, parts }) => ({ model, amount: parts == null ? null : toScaledInteger(parts, scale) }));

  const knownRows = exactRows.filter((entry): entry is { model: ModelSpendRecord; amount: bigint } => entry.amount != null);
  const rowTotal = knownRows.reduce((sum, entry) => sum + entry.amount, 0n);

  if (rowTotal !== total) return { state: "incomplete", reason: "The model spend breakdown does not reconcile to the selected-period total." };

  if (total === 0n) return { state: "empty", totalSpendUsd: formatScaledUsd(total, scale) };

  const entries = knownRows.filter(({ amount }) => amount > 0n);
  const small = entries.filter(({ amount }) => amount * 100n < total * 3n);
  const visible = entries.filter(({ amount }) => amount * 100n >= total * 3n);
  const normalized = visible.map(({ model, amount }) => ({ id: model.id, name: `${model.providerName} / ${model.modelId}`, amount, requests: model.requests }));

  if (small.length) normalized.push({ id: "other-models", name: "Other models", amount: small.reduce((sum, entry) => sum + entry.amount, 0n), requests: small.reduce((sum, entry) => sum + entry.model.requests, 0) });

  const slices = normalized.map(({ id, name, amount, requests }) => ({
    id,
    name,
    spendUsd: formatScaledUsd(amount, scale),
    value: Number((amount * 1_000_000_000n) / total) / 1_000_000_000,
    percent: Number((amount * 10_000n + total / 2n) / total) / 100,
    requests,
  }));

  return { state: "ready", totalSpendUsd: formatScaledUsd(total, scale), slices };
}
