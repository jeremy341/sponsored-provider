import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import type { PersonRecord } from "../contracts/api";
import { remainingUsd } from "../lib/money";
import { AllowanceSummary } from "./developer/AllowanceSummary";
import { AllowanceEditor } from "./operator/people/AllowanceEditor";

const monthlyAllowance = {
  usedUsd: "1.25",
  reservedUsd: "0.25",
  consumedUsd: "1.50",
  limitUsd: "7",
  remainingUsd: "5.50",
  period: "monthly",
  resetAt: "2026-10-01T00:00:00+02:00",
  source: "gateway estimate",
};

const person = {
  id: "developer-1",
  displayName: "Developer One",
  email: null,
  status: "active",
  allowanceUsd: "7",
  allowancePeriod: "monthly",
  rpmLimit: 30,
  usedUsd: "1.25",
  reservedUsd: "0.25",
  allowanceResetAt: "2026-10-01T00:00:00+02:00",
  keyCount: 2,
  requestCount: 4,
  lastActiveAt: null,
} satisfies PersonRecord;

describe("monthly developer allowance", () => {
  it("subtracts usage and reservations without losing nano-dollar precision", () => {
    expect(remainingUsd("7", "1.25", "0.250000001")).toBe("5.499999999");
    expect(remainingUsd("7", null, "0")).toBeNull();
  });

  it("shows the server-provided seven dollar monthly allowance and Berlin reset", () => {
    render(<AllowanceSummary allowance={monthlyAllowance} />);

    expect(screen.getByText("$7/month")).toBeInTheDocument();
    expect(screen.getByText(/shared across your keys/i)).toBeInTheDocument();
    expect(screen.getByText(/1 October 2026 · 00:00 Berlin/i)).toBeInTheDocument();
  });

  it("allows an operator to save a monthly per-person allowance", async () => {
    const save = vi.fn().mockResolvedValue(undefined);

    render(<AllowanceEditor person={person} onSave={save} />);
    await userEvent.selectOptions(screen.getByLabelText("Allowance period"), "monthly");
    await userEvent.click(screen.getByRole("button", { name: "Save allowance" }));

    await waitFor(() => expect(save).toHaveBeenCalledWith({ allowanceUsd: "7", allowancePeriod: "monthly", rpmLimit: 30 }));
  });
});
