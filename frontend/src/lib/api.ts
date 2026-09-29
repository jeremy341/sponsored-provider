import type {
  ActivityEvent,
  DeveloperProviderStatus,
  OperatorSystemSnapshot,
  ApiKeyRecord,
  CreateKeyInput,
  CreateKeyResult,
  CreateInviteResult,
  CreateProviderInput,
  DeveloperActivityFilter,
  CreateProviderResponse,
  SyncProviderResponse,
  DeveloperDashboard,
  DashboardRange,
  GuardrailSnapshot,
  ModelRecord,
  ModelPolicyInput,
  OperatorDashboard,
  OperatorUsageFilter,
  Page,
  PersonRecord,
  PortalApi,
  ProviderConnectionRecord,
  CatalogOfferRecord,
  PriceVersionRecord,
  UpdateKeyPolicyInput,
} from "../contracts/api";

export class ApiError extends Error {
  constructor(message: string, readonly status: number, readonly code: string | null = null) {
    super(message);
    this.name = "ApiError";
  }
}

interface SessionResponse {
  user: { displayName: string; email: string | null };
  role: "operator" | "developer";
  csrfToken: string;
}

let csrfToken: string | null = null;

export function getCsrfToken(): string | null {
  return csrfToken;
}

async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  const preview = new URLSearchParams(window.location.search).get("preview");

  if (import.meta.env.DEV && (preview === "developer" || preview === "operator") && init.method && init.method !== "GET") {
    throw new ApiError("This read-only layout preview does not send changes to an API.", 403);
  }

  const headers = new Headers(init.headers);
  headers.set("Accept", "application/json");

  if (init.body) headers.set("Content-Type", "application/json");

  if (csrfToken && init.method && init.method !== "GET") headers.set("X-CSRF-Token", csrfToken);

  let response: Response;

  try {
    response = await fetch(path, { ...init, headers, credentials: "same-origin", redirect: "error" });
  } catch {
    throw new ApiError("The portal API could not be reached. Check the connection and try again.", 0);
  }

  if (!response.ok) {
    if (path === "/auth/signup") {
      const detail = response.status === 403
        ? "This invitation is invalid, expired, revoked, exhausted, or email-bound. Ask the operator for a new invitation."
        : "Account creation failed. Check the username, password, and invitation, then try again.";

      throw new ApiError(detail, response.status);
    }

    const message = path === "/api/operator/providers" && response.status === 502
      ? "Initial /models test and discovery failed. The connection was saved; check the URL and credential, then retry sync."
      : response.status === 401
      ? path === "/auth/login" ? "Invalid username or password" : "Your session has expired. Sign in again to continue."
      : response.status === 403
        ? "Your account does not have access to this action."
        : response.status === 404
          ? "This portal API is not available on the connected server yet."
          : `The request failed (${response.status}). Try again or contact the operator.`;

    throw new ApiError(message, response.status);
  }

  return response.json();
}

async function requestVoid(path: string, init: RequestInit): Promise<void> {
  const preview = new URLSearchParams(window.location.search).get("preview");

  if (import.meta.env.DEV && (preview === "developer" || preview === "operator")) {
    throw new ApiError("This read-only layout preview does not send changes to an API.", 403);
  }

  const headers = new Headers(init.headers);
  headers.set("Accept", "application/json");

  if (init.body) headers.set("Content-Type", "application/json");

  if (csrfToken && init.method && init.method !== "GET") headers.set("X-CSRF-Token", csrfToken);

  let response: Response;

  try {
    response = await fetch(path, { ...init, headers, credentials: "same-origin", redirect: "error" });
  } catch {
    throw new ApiError("The portal API could not be reached. Check the connection and try again.", 0);
  }

  if (!response.ok) {
    const message = response.status === 401
      ? "Your session has expired. Sign in again to continue."
      : response.status === 403
        ? "Your account does not have access to this action."
        : `The request failed (${response.status}). Try again or contact the operator.`;

    throw new ApiError(message, response.status);
  }
}

export const api: PortalApi = {
  async getSession() {
    const session = await request<SessionResponse>("/api/session");
    csrfToken = session.csrfToken;

    return session;
  },
  async logout() {
    await requestVoid("/auth/logout", { method: "POST" });
    csrfToken = null;
  },
  localLogin: (input) => request("/auth/login", { method: "POST", body: JSON.stringify(input) }),
  localSignup: (input) => request("/auth/signup", { method: "POST", body: JSON.stringify(input) }),
  getDeveloperDashboard: (range: DashboardRange = "current_month") => request<DeveloperDashboard>(`/api/developer/dashboard?range=${range}`),
  getOperatorDashboard: (range: DashboardRange = "current_month") => request<OperatorDashboard>(`/api/operator/dashboard?range=${range}`),
  listKeys: () => request<ApiKeyRecord[]>("/api/developer/keys"),
  createKey: (input: CreateKeyInput) => request<CreateKeyResult>("/api/developer/keys", { method: "POST", body: JSON.stringify(input) }),
  updateKeyPolicy: (keyId, input: UpdateKeyPolicyInput) => request<ApiKeyRecord>(`/api/developer/keys/${encodeURIComponent(keyId)}`, { method: "PATCH", body: JSON.stringify(input) }),
  revokeKey: (keyId) => requestVoid(`/api/developer/keys/${encodeURIComponent(keyId)}/revoke`, { method: "POST" }),
  archiveKey: (keyId) => requestVoid(`/api/developer/keys/${encodeURIComponent(keyId)}/archive`, { method: "POST" }),
  listModels: () => request<ModelRecord[]>("/api/models"),
  listActivity: (filters: DeveloperActivityFilter = {}) => {
    const params = new URLSearchParams();
    Object.entries(filters).forEach(([key, value]) => { if (value != null && value !== "") params.set(key, String(value)); });

    return request<Page<ActivityEvent>>(`/api/activity${params.size ? `?${params}` : ""}`);
  },
  listOperatorActivity: (filters: OperatorUsageFilter = {}) => {
    const params = new URLSearchParams();
    Object.entries(filters).forEach(([key, value]) => { if (value != null && value !== "") params.set(key, String(value)); });

    return request<Page<ActivityEvent>>(`/api/operator/usage${params.size ? `?${params}` : ""}`);
  },
  listPeople: () => request<PersonRecord[]>("/api/operator/people"),
  listProviders: () => request<ProviderConnectionRecord[]>("/api/operator/providers"),
  listOperatorOffers: () => request<CatalogOfferRecord[]>("/api/operator/offers"),
  listOperatorModels: () => request<ModelRecord[]>("/api/operator/models"),
  getGuardrails: () => request<GuardrailSnapshot>("/api/operator/guardrails"),
  createProvider: (input: CreateProviderInput) => request<CreateProviderResponse>("/api/operator/providers", { method: "POST", body: JSON.stringify(input) }),
  syncProvider: (providerId) => request<SyncProviderResponse>(`/api/operator/providers/${encodeURIComponent(providerId)}/sync`, { method: "POST" }),
  updateOfferPrice: (offerId, input: PriceVersionRecord) => request<{ id: string; offerId: string; status: string }>(`/api/operator/offers/${encodeURIComponent(offerId)}/price`, { method: "PATCH", body: JSON.stringify({ inputUsdPerMillion: input.inputUsdPerMillion, outputUsdPerMillion: input.outputUsdPerMillion, cachedInputUsdPerMillion: input.cachedInputUsdPerMillion, source: input.source }) }),
  approveOfferPrice: (offerId, versionId) => requestVoid(`/api/operator/offers/${encodeURIComponent(offerId)}/prices/${encodeURIComponent(versionId)}/approve`, { method: "POST" }),
  setOfferAvailable: (offerId, enabled) => requestVoid(`/api/operator/offers/${encodeURIComponent(offerId)}/availability`, { method: "PATCH", body: JSON.stringify({ enabled }) }),
  setRouteAvailability: (routeId, enabled) => requestVoid(`/api/operator/routes/${encodeURIComponent(routeId)}/availability`, { method: "PATCH", body: JSON.stringify({ enabled }) }),
  updateRouteOrder: (offerId, connectionIds) => requestVoid(`/api/operator/offers/${encodeURIComponent(offerId)}/routes`, { method: "PATCH", body: JSON.stringify({ connectionIds }) }),
  mapConnectionModel: (connectionId, upstreamModelId, offerId) => requestVoid(`/api/operator/connections/${encodeURIComponent(connectionId)}/models/mapping`, { method: "PATCH", body: JSON.stringify({ upstreamModelId, offerId }) }),
  updateConnectionBudget: (connectionId, input) => requestVoid(`/api/operator/connections/${encodeURIComponent(connectionId)}/budget`, { method: "POST", body: JSON.stringify(input) }),
  setModelPolicy: (providerId, modelId, policy: ModelPolicyInput) => requestVoid(`/api/operator/providers/${encodeURIComponent(providerId)}/models/${encodeURIComponent(modelId)}`, { method: "PUT", body: JSON.stringify(policy) }),
  createInvite: (input) => request<CreateInviteResult>("/api/operator/invites", { method: "POST", body: JSON.stringify(input) }),
  listOperatorInvites: () => request("/api/operator/invites"),
  revokeInvite: (inviteId) => request(`/api/operator/invites/${encodeURIComponent(inviteId)}/revoke`, { method: "POST" }),
  getDeveloperInvites: () => request("/api/developer/invites"),
  createDeveloperInvite: () => request("/api/developer/invites", { method: "POST", body: "{}" }),
  updatePersonPolicy: (userId, input) => requestVoid(`/api/operator/people/${encodeURIComponent(userId)}/policy`, { method: "PATCH", body: JSON.stringify(input) }),
  setPersonEnabled: (userId, enabled) => requestVoid(`/api/operator/people/${encodeURIComponent(userId)}/${enabled ? "enable" : "disable"}`, { method: "POST" }),
  setGlobalStop: (stopped) => requestVoid("/api/operator/guardrails", { method: "PATCH", body: JSON.stringify({ globalStopped: stopped }) }),
  updateGuardrails: (input) => requestVoid("/api/operator/guardrails", { method: "PATCH", body: JSON.stringify(input) }),
  blockIp: (input) => requestVoid("/api/operator/blocked-ips", { method: "POST", body: JSON.stringify(input) }),
  unblockIp: (ip) => requestVoid(`/api/operator/blocked-ips/${encodeURIComponent(ip)}`, { method: "DELETE" }),
};

export const apiExtensions = {
  listDeveloperProviders: () => request<DeveloperProviderStatus[]>("/api/developer/providers"),
  getDeveloperRequest: (requestId: string) => request<ActivityEvent & { stream?: boolean; origin?: string | null; priceSnapshot?: { input: number; output: number; cache: number } | null }>(`/api/developer/requests/${encodeURIComponent(requestId)}`),
  getOperatorSystem: () => request<OperatorSystemSnapshot>("/api/operator/system"),
};

/**
 * Playground inference: same-origin POST that streams the exact /v1 SSE the
 * gateway produces. Telemetry deltas are reported through onTelemetry.
 */
export async function streamPlayground(options: {
  keyId: string;
  payload: Record<string, unknown>;
  signal: AbortSignal;
  onTelemetry: (event: { ttftMs?: number; firstChunkAt?: number; error?: string | null; errorCode?: string | null }) => void;
}): Promise<{ text: string; error: string | null; errorCode: string | null; usage: { input: number | null; output: number | null; total: number | null } | null }> {
  const headers = new Headers({ "Content-Type": "application/json" });
  const csrf = getCsrfToken();
  if (csrf) headers.set("X-CSRF-Token", csrf);

  let response: Response;
  const started = performance.now();
  let firstChunkAt: number | null = null;

  try {
    response = await fetch("/api/developer/playground", {
      method: "POST",
      headers,
      credentials: "same-origin",
      signal: options.signal,
      body: JSON.stringify({ keyId: options.keyId, payload: options.payload }),
    });
  } catch (error) {
    if ((error as Error).name === "AbortError") throw error;
    throw new ApiError("The gateway could not be reached. Check the connection and try again.", 0);
  }

  if (!response.ok) {
    let message = `The request failed (${response.status}).`;
    let code: string | null = null;
    try {
      const body = await response.json();
      message = body?.error?.message ?? message;
      code = body?.error?.code ?? null;
    } catch {
      // Non-JSON error body: keep the generic message.
    }
    throw new ApiError(message, response.status, code);
  }

  const contentType = response.headers.get("content-type") ?? "";
  let text = "";
  let streamError: string | null = null;
  let streamErrorCode: string | null = null;
  let usage: { input: number | null; output: number | null; total: number | null } | null = null;

  if (contentType.includes("text/event-stream")) {
    const reader = response.body?.getReader();
    if (!reader) throw new ApiError("The gateway returned an unreadable stream.", 0);
    const decoder = new TextDecoder();
    let buffer = "";

    for (;;) {
      const { done, value } = await reader.read();
      if (done) break;
      if (firstChunkAt == null) {
        firstChunkAt = performance.now() - started;
        options.onTelemetry({ ttftMs: firstChunkAt });
      }
      buffer += decoder.decode(value, { stream: true });
      let boundary = buffer.indexOf("\n\n");
      while (boundary !== -1) {
        const rawEvent = buffer.slice(0, boundary);
        buffer = buffer.slice(boundary + 2);
        boundary = buffer.indexOf("\n\n");
        const line = rawEvent.split("\n").find((candidate) => candidate.startsWith("data:"));
        if (!line) continue;
        const data = line.slice(5).trim();
        if (!data || data === "[DONE]") continue;
        try {
          const parsed = JSON.parse(data) as { error?: { message?: string; code?: string }; choices?: Array<{ delta?: { content?: string | null }; text?: string }> };
          if (parsed.error) {
            streamError = parsed.error.message ?? "The upstream request failed.";
            streamErrorCode = parsed.error.code ?? null;
            options.onTelemetry({ error: streamError, errorCode: streamErrorCode });
            continue;
          }
          const delta = parsed.choices?.[0]?.delta?.content ?? parsed.choices?.[0]?.text ?? "";
          if (delta) text += delta;
        } catch {
          // Ignore malformed keep-alive frames.
        }
      }
    }
  } else {
    firstChunkAt = performance.now() - started;
    options.onTelemetry({ ttftMs: firstChunkAt });
    const body = (await response.json()) as {
      choices?: Array<{ message?: { content?: string } }>;
      usage?: { prompt_tokens?: number; completion_tokens?: number; total_tokens?: number } | null;
      error?: { message?: string; code?: string };
    };
    if (body?.error) {
      streamError = body.error.message ?? "The upstream request failed.";
      streamErrorCode = body.error.code ?? null;
    } else {
      text = body?.choices?.[0]?.message?.content ?? "";
      if (body?.usage) {
        usage = {
          input: body.usage.prompt_tokens ?? null,
          output: body.usage.completion_tokens ?? null,
          total: body.usage.total_tokens ?? null,
        };
      }
    }
  }

  options.onTelemetry({});
  return { text, error: streamError, errorCode: streamErrorCode, usage };
}
