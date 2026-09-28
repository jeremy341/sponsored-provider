import { afterEach, describe, expect, it, vi } from "vitest";
import { api } from "./api";

afterEach(() => vi.unstubAllGlobals());

describe("developer activity API query", () => {
  it("requests the selected dashboard analytics range and defaults to current month", async () => {
    const fetchMock = vi.fn().mockImplementation(() => Promise.resolve(new Response(JSON.stringify({}), {
      status: 200, headers: { "Content-Type": "application/json" },
    })));

    vi.stubGlobal("fetch", fetchMock);

    await api.getDeveloperDashboard();
    await api.getDeveloperDashboard("30d");

    expect(String(fetchMock.mock.calls[0][0])).toBe("/api/developer/dashboard?range=current_month");
    expect(String(fetchMock.mock.calls[1][0])).toBe("/api/developer/dashboard?range=30d");
  });

  it("sends model, key, date, and outcome filters to the owner-scoped server endpoint", async () => {
    const fetchMock = vi.fn().mockResolvedValue(new Response(JSON.stringify({ items: [], nextCursor: null }), {
      status: 200, headers: { "Content-Type": "application/json" },
    }));

    vi.stubGlobal("fetch", fetchMock);

    await api.listActivity({ cursor: "2026-09-27T10:00:00Z|event-1", limit: 25, model: "qwen", keyId: "key-1", from: "2026-09-26", to: "2026-09-27", outcome: "rejected" });

    expect(fetchMock).toHaveBeenCalledWith(expect.stringMatching(/^\/api\/activity\?/), expect.any(Object));
    const url = new URL(String(fetchMock.mock.calls[0][0]), "https://portal.example.test");
    expect(url.searchParams.get("cursor")).toBe("2026-09-27T10:00:00Z|event-1");
    expect(url.searchParams.get("limit")).toBe("25");
    expect(url.searchParams.get("model")).toBe("qwen");
    expect(url.searchParams.get("keyId")).toBe("key-1");
    expect(url.searchParams.get("from")).toBe("2026-09-26");
    expect(url.searchParams.get("to")).toBe("2026-09-27");
    expect(url.searchParams.get("outcome")).toBe("rejected");
  });
});
