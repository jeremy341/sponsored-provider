import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";
import { api } from "../lib/api";
import type { DeveloperInviteStatus, InviteRecord } from "../contracts/api";
import { DeveloperInviteCard, InviteDialog } from "./App";

const activeLegacyInvite: InviteRecord = {
  id: "legacy-1",
  bound_email: "old@example.test",
  expires_at: "2026-10-03T00:00:00+00:00",
  max_uses: 3,
  uses_count: 1,
  revoked_at: null,
  created_at: "2026-09-26T00:00:00+00:00",
  status: "active",
  email_bound: true,
};

afterEach(() => {
  vi.restoreAllMocks();
  vi.unstubAllGlobals();
});

describe("invite controls", () => {
  it("creates with default limits, marks legacy bound invites, and confirms revocation", async () => {
    const revokedInvite = { ...activeLegacyInvite, revoked_at: "2026-09-27T00:00:00+00:00", status: "revoked" as const };
    vi.spyOn(api, "listOperatorInvites")
      .mockResolvedValueOnce([activeLegacyInvite])
      .mockResolvedValue([revokedInvite]);

    const create = vi.spyOn(api, "createInvite").mockResolvedValue({
      invite: { id: "new-1", bound_email: null, expires_at: "2026-10-03T00:00:00+00:00", max_uses: 5, uses_count: 0, revoked_at: null, created_at: "2026-09-26T00:00:00+00:00" },
      invite_token: "secret-once",
    });

    const revoke = vi.spyOn(api, "revokeInvite").mockResolvedValue(revokedInvite);
    const confirm = vi.fn(() => true);
    vi.stubGlobal("confirm", confirm);
    const setToken = vi.fn();

    render(<InviteDialog open onOpenChange={vi.fn()} token={null} setToken={setToken} />);
    expect(await screen.findByText("Email-bound legacy invite")).toBeInTheDocument();
    expect(screen.getByText(/cannot be used for local signup/i)).toBeInTheDocument();
    expect(screen.getByLabelText("Maximum uses")).toHaveValue(5);
    expect(screen.getByLabelText("Expires in (days)")).toHaveValue(7);
    expect(screen.queryByLabelText(/email/i)).not.toBeInTheDocument();

    await userEvent.click(screen.getByRole("button", { name: "Revoke" }));
    expect(confirm).toHaveBeenCalledOnce();
    expect(revoke).toHaveBeenCalledWith("legacy-1");
    await waitFor(() => expect(screen.getByText("revoked")).toBeInTheDocument());

    await userEvent.click(screen.getByRole("button", { name: "Create invite" }));
    await waitFor(() => expect(create).toHaveBeenCalledWith({ max_uses: 5, expires_in_seconds: 604800 }));
    expect(setToken).toHaveBeenCalledWith("secret-once");
  });

  it("reveals a developer invite once and shows safe used status without token after reload", async () => {
    const beforeIssue: DeveloperInviteStatus = { entitled: true, can_issue: true, issued_at: null, invite: null };

    const afterIssue: DeveloperInviteStatus = {
      entitled: true,
      can_issue: false,
      issued_at: "2026-09-26T00:00:00+00:00",
      invite: { id: "dev-1", expires_at: "2026-10-03T00:00:00+00:00", max_uses: 1, uses_count: 0, revoked_at: null, created_at: "2026-09-26T00:00:00+00:00", status: "active" },
    };

    vi.spyOn(api, "getDeveloperInvites").mockResolvedValueOnce(beforeIssue).mockResolvedValue(afterIssue);
    vi.spyOn(api, "createDeveloperInvite").mockResolvedValue({
      invite: { id: "dev-1", expires_at: afterIssue.invite!.expires_at, max_uses: 1, uses_count: 0, revoked_at: null, created_at: afterIssue.issued_at! },
      invite_token: "developer-secret",
    });
    const view = render(<DeveloperInviteCard />);
    await userEvent.click(await screen.findByRole("button", { name: "Create invite" }));
    const link = await screen.findByLabelText("Invitation link");
    expect(link).toHaveValue(`${window.location.origin}/auth/login#invite=developer-secret`);
    expect(link.getAttribute("value")).not.toContain("?invite=");

    view.unmount();
    render(<DeveloperInviteCard />);
    expect(await screen.findByText("active")).toBeInTheDocument();
    expect(screen.getByText(/0\/1 uses/)).toBeInTheDocument();
    expect(screen.queryByLabelText("Invitation link")).not.toBeInTheDocument();
    expect(screen.queryByText("developer-secret")).not.toBeInTheDocument();
  });
});
