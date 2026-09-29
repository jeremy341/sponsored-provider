import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";
import type { InviteRecord, OperatorSystemSnapshot } from "../../contracts/api";
import { api, apiExtensions } from "../../lib/api";
import { SystemPage } from "./SystemPage";
import { InvitesPage } from "./InvitesPage";
import { SettingsPage } from "../console/SettingsPage";

const system: OperatorSystemSnapshot = {
  version: "0.1.0",
  uptimeSeconds: 7342,
  pythonVersion: "3.12.1",
  platform: "Linux-6.1.0-x86_64",
  inference: { stopped: false, stopSource: null, globalSpendCapUsd: 25, safetyReserveUsd: 2.5 },
  jobs: { lastProviderSyncAt: "2026-09-29T09:30:00Z", backupStatus: "not_configured", lastBackupAt: null, lastRestoreTestAt: null },
  database: { engine: "sqlite", sqliteVersion: "3.45.0", path: "provider.db", sizeBytes: 524288, tableCount: 23, schemaVersion: 12 },
  counts: { users: 4, activeApiKeys: 6, providerConnections: 2, activeOffers: 9, usageEvents30d: 512 },
};

const invite: InviteRecord = {
  id: "inv-1",
  bound_email: null,
  expires_at: "2026-10-06T10:00:00Z",
  max_uses: 1,
  uses_count: 0,
  revoked_at: null,
  created_at: "2026-09-29T10:00:00Z",
  status: "active",
  email_bound: false,
};

describe("operator system", () => {
  afterEach(() => vi.restoreAllMocks());

  it("renders live deployment facts and reports backups honestly", async () => {
    vi.spyOn(apiExtensions, "getOperatorSystem").mockResolvedValue(system);
    render(<MemoryRouter><SystemPage /></MemoryRouter>);

    expect(await screen.findByText("0.1.0")).toBeInTheDocument();
    expect(screen.getByText(/Accepting sponsored requests/)).toBeInTheDocument();
    const database = screen.getByRole("article", { name: "Database" });
    expect(within(database).getAllByText(/sqlite/).length).toBeGreaterThan(0);
    expect(screen.getByText("Not configured")).toBeInTheDocument();
    expect(screen.getByText("Never run")).toBeInTheDocument();
    expect(screen.getByText("512")).toBeInTheDocument();
  });

  it("marks an active stop with its source", async () => {
    vi.spyOn(apiExtensions, "getOperatorSystem").mockResolvedValue({
      ...system,
      inference: { stopped: true, stopSource: "operator_stop", globalSpendCapUsd: 25, safetyReserveUsd: 2.5 },
    });
    render(<MemoryRouter><SystemPage /></MemoryRouter>);

    expect(await screen.findByText(/Operator stop active/)).toBeInTheDocument();
  });
});

describe("operator invites", () => {
  afterEach(() => {
    vi.restoreAllMocks();
    window.localStorage.clear();
  });

  it("lists invites with status and single-use counters", async () => {
    vi.spyOn(api, "listOperatorInvites").mockResolvedValue([invite]);
    render(<MemoryRouter><InvitesPage /></MemoryRouter>);

    expect(await screen.findByText("active", { exact: false })).toBeInTheDocument();
    expect(screen.getByText("0/1")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "New invite" })).toBeEnabled();
  });

  it("creates an invite and shows the raw link exactly once", async () => {
    vi.spyOn(api, "listOperatorInvites").mockResolvedValue([invite]);
    vi.spyOn(api, "createInvite").mockResolvedValue({
      invite: { id: "inv-2", bound_email: null, expires_at: "2026-10-06T10:00:00Z", max_uses: 1, uses_count: 0, revoked_at: null, created_at: "2026-09-29T12:00:00Z" },
      invite_token: "raw-token-value",
    });
    render(<MemoryRouter><InvitesPage /></MemoryRouter>);

    await screen.findByText("0/1");
    await userEvent.click(screen.getByRole("button", { name: "New invite" }));

    const link = await screen.findByLabelText("Invitation link");
    expect((link as HTMLInputElement).value).toContain("raw-token-value");
    expect((link as HTMLInputElement).value).toContain("/auth/login#invite=");
  });
});

describe("settings", () => {
  afterEach(() => {
    vi.restoreAllMocks();
    window.localStorage.clear();
    delete document.documentElement.dataset.accent;
    delete document.documentElement.dataset.density;
  });

  it("shows the signed-in account facts and privacy summary", async () => {
    vi.spyOn(api, "getSession").mockResolvedValue({
      user: { displayName: "Ada Dev", email: "ada@example.test" },
      role: "developer",
      csrfToken: "token-1",
    });
    render(<MemoryRouter><SettingsPage /></MemoryRouter>);

    expect(await screen.findByText("Ada Dev")).toBeInTheDocument();
    expect(screen.getByText("ada@example.test")).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Privacy" }));
    expect(screen.getByText(/metadata only/i)).toBeInTheDocument();
    expect(screen.getByText(/never persisted/i)).toBeInTheDocument();
  });

  it("persists the accent choice to the document and local storage", async () => {
    vi.spyOn(api, "getSession").mockResolvedValue({
      user: { displayName: "Ada Dev", email: null },
      role: "developer",
      csrfToken: "token-1",
    });
    render(<MemoryRouter><SettingsPage /></MemoryRouter>);

    await screen.findByText("Ada Dev");
    await userEvent.click(screen.getByRole("button", { name: "Appearance" }));
    await userEvent.click(await screen.findByRole("radio", { name: "Cyan" }));

    await waitFor(() => {
      expect(document.documentElement.dataset.accent).toBe("cyan");
      expect(window.localStorage.getItem("provider.accent")).toBe("cyan");
    });
  });
});
