import type {
  ActivityEvent,
  ApiKeyRecord,
  CreateKeyInput,
  CreateKeyResult,
  CreateInviteResult,
  CreateProviderInput,
  CreateProviderResponse,
  SyncProviderResponse,
  DeveloperDashboard,
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
  constructor(message: string, readonly status: number) {
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
  getDeveloperDashboard: () => request<DeveloperDashboard>("/api/developer/dashboard"),
  getOperatorDashboard: () => request<OperatorDashboard>("/api/operator/dashboard"),
  listKeys: () => request<ApiKeyRecord[]>("/api/developer/keys"),
  createKey: (input: CreateKeyInput) => request<CreateKeyResult>("/api/developer/keys", { method: "POST", body: JSON.stringify(input) }),
  updateKeyPolicy: (keyId, input: UpdateKeyPolicyInput) => request<ApiKeyRecord>(`/api/developer/keys/${encodeURIComponent(keyId)}`, { method: "PATCH", body: JSON.stringify(input) }),
  revokeKey: (keyId) => requestVoid(`/api/developer/keys/${encodeURIComponent(keyId)}/revoke`, { method: "POST" }),
  archiveKey: (keyId) => requestVoid(`/api/developer/keys/${encodeURIComponent(keyId)}/archive`, { method: "POST" }),
  listModels: () => request<ModelRecord[]>("/api/models"),
  listActivity: (cursor) => request<Page<ActivityEvent>>(`/api/activity${cursor ? `?cursor=${encodeURIComponent(cursor)}` : ""}`),
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
