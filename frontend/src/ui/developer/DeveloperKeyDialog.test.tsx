import { afterEach, describe, expect, it, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { CreateKeyDialog } from "../App";
import { api } from "../../lib/api";
import type { ApiKeyRecord, ModelRecord } from "../../contracts/api";

const models: ModelRecord[] = [
  { id: "acme::model-a", displayName: "Model A", providerName: "Acme AI", capabilities: ["text"], inputUsdPerMillion: "0.3", outputUsdPerMillion: "1.2", cacheUsdPerMillion: null, pricingVerified: true, priceSource: "verified", approved: true, available: true, syncedAt: null, activeRouteCount: null },
  { id: "acme::model-b", displayName: "Model B", providerName: "Acme AI", capabilities: ["text"], inputUsdPerMillion: "0.5", outputUsdPerMillion: "1.5", cacheUsdPerMillion: null, pricingVerified: true, priceSource: "verified", approved: true, available: true, syncedAt: null, activeRouteCount: null },
];

const createdKey: ApiKeyRecord = {
  id: "key-1", label: "OpenCode", prefix: "sp_sk_test", modelAccess: { mode: "all_approved" }, spendCapUsd: null,
  spendUsedUsd: null, spendPeriod: null, spendResetAt: null, rpmLimit: null, createdAt: "2026-09-27T00:00:00Z", lastUsedAt: null, status: "active",
};

afterEach(() => vi.restoreAllMocks());

function renderDialog() {
  return render(<CreateKeyDialog open onOpenChange={vi.fn()} created={null} onCreated={vi.fn()} onSaved={vi.fn()} />);
}

describe("developer key model policy", () => {
  it("creates a key with all published models by default", async () => {
    vi.spyOn(api, "listModels").mockResolvedValue(models);
    const create = vi.spyOn(api, "createKey").mockResolvedValue({ key: createdKey, secret: "sp_sk_once" });
    renderDialog();
    expect(await screen.findByRole("radio", { name: /All published models/i })).toBeChecked();
    await userEvent.type(screen.getByLabelText(/Key name/i), "OpenCode");
    await userEvent.click(screen.getByRole("button", { name: /Create key/i }));
    await waitFor(() => expect(create).toHaveBeenCalledWith(expect.objectContaining({ label: "OpenCode", modelAccess: { mode: "all_approved" } })));
  });

  it("stores selected stable public model IDs and labels the key cap as a sublimit", async () => {
    vi.spyOn(api, "listModels").mockResolvedValue(models);
    const create = vi.spyOn(api, "createKey").mockResolvedValue({ key: createdKey, secret: "sp_sk_once" });
    renderDialog();
    await userEvent.type(screen.getByLabelText(/Key name/i), "OpenCode");
    await userEvent.click(screen.getByRole("radio", { name: /Choose specific models/i }));
    await userEvent.click(await screen.findByRole("checkbox", { name: /acme::model-a/i }));
    await userEvent.click(screen.getByRole("checkbox", { name: /acme::model-b/i }));
    expect(screen.getByText(/key cap can only tighten your account allowance/i)).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: /Create key/i }));
    await waitFor(() => expect(create).toHaveBeenCalledWith(expect.objectContaining({ modelAccess: { mode: "selected", modelIds: ["acme::model-a", "acme::model-b"] } })));
  });
});
