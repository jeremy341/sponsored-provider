export type ModelAccess =
  | { mode: "all_approved" }
  | { mode: "selected"; modelIds: string[] };

export interface UsageSummary {
  requests: number;
  successfulRequests: number;
  rejectedRequests: number;
  inputTokens: number | null;
  outputTokens: number | null;
  totalTokens: number | null;
  estimatedSpendUsd: number | null;
  allowanceUsedUsd: number | null;
  allowanceLimitUsd: number | null;
  p95LatencyMs: number | null;
  sampleCount: number;
  period: string;
  source: "gateway_estimate" | "provider_reported" | "mixed";
}

export interface UsagePoint {
  day: string;
  requests: number;
  total_tokens: number | null;
  estimated_spend_usd: number | null;
}

export interface ModelUsageRecord {
  modelId: string;
  providerName: string;
  requests: number;
  totalTokens: number | null;
  estimatedSpendUsd: number | null;
}

export interface ActivityEvent {
  id: string;
  occurredAt: string;
  modelId: string;
  providerName: string;
  keyLabel: string;
  inputTokens: number | null;
  outputTokens: number | null;
  totalTokens: number | null;
  estimatedCostUsd: number | null;
  costSource: "gateway_estimate" | "provider_reported" | "unknown";
  status: "success" | "error" | "rejected" | "interrupted";
  errorCategory: string | null;
  latencyMs: number | null;
  cachedTokens: number | null;
  requestIp?: string;
}

export interface ApiKeyRecord {
  id: string;
  label: string;
  prefix: string;
  modelAccess: ModelAccess;
  spendCapUsd: number | null;
  spendUsedUsd: number | null;
  spendPeriod: "day" | "week" | "month" | "lifetime" | null;
  spendResetAt: string | null;
  rpmLimit: number | null;
  createdAt: string;
  lastUsedAt: string | null;
  status: "active" | "disabled" | "archived";
}

export interface ModelRecord {
  id: string;
  upstreamModelId?: string;
  providerId?: string;
  providerName: string;
  capabilities: Array<"text" | "vision">;
  inputUsdPerMillion: number | null;
  outputUsdPerMillion: number | null;
  cacheUsdPerMillion: number | null;
  pricingVerified: boolean;
  priceSource?: string | null;
  approved: boolean;
  available: boolean;
  syncedAt: string | null;
}

export interface PersonRecord {
  id: string;
  displayName: string;
  email: string | null;
  status: "active" | "pending" | "disabled";
  allowanceUsd: number | null;
  allowancePeriod: "day" | "week" | null;
  rpmLimit: number | null;
  usedUsd: number | null;
  keyCount: number;
  requestCount: number;
  lastActiveAt: string | null;
}

export interface ProviderRecord {
  id: string;
  name: string;
  baseUrlDisplay: string;
  enabled: boolean;
  health: "healthy" | "degraded" | "unknown" | "disabled";
  lastSyncAt: string | null;
  discoveredModels: number;
  approvedModels: number;
}

export interface CreateProviderInput {
  name: string;
  baseUrl: string;
  apiKey: string;
}

export interface ModelPolicyInput {
  inputUsdPerMillion: number;
  outputUsdPerMillion: number;
  cacheUsdPerMillion: number | null;
  priceSource: string;
  capabilities: Array<"text" | "vision">;
  approved: boolean;
}

export interface CreateInviteResult {
  invite: { id: string; bound_email?: string | null; expires_at: string; max_uses: number; uses_count: number; revoked_at: string | null; created_at: string };
  invite_token: string;
}

export interface InviteRecord {
  id: string;
  bound_email: string | null;
  expires_at: string;
  max_uses: number;
  uses_count: number;
  revoked_at: string | null;
  created_at: string;
  status: "active" | "exhausted" | "expired" | "revoked";
  email_bound: boolean;
}

export interface DeveloperInviteStatus {
  entitled: boolean;
  can_issue: boolean;
  issued_at: string | null;
  invite: null | {
    id: string;
    expires_at: string;
    max_uses: number;
    uses_count: number;
    revoked_at: string | null;
    created_at: string;
    status: "active" | "exhausted" | "expired" | "revoked";
  };
}

export interface GuardrailSnapshot {
  globalSpendCapUsd: number | null;
  globalSpendUsedUsd: number | null;
  safetyReserveUsd: number | null;
  globalStopped: boolean;
  blockedIps: Array<{ ip: string; reason: string | null; createdAt: string }>;
  recentAudit: Array<{
    id: string;
    actor: string;
    action: string;
    target: string;
    occurredAt: string;
  }>;
}

export interface DeveloperDashboard {
  usage: UsageSummary | null;
  series: UsagePoint[];
  topModels: ModelUsageRecord[];
  keys: ApiKeyRecord[];
  recentActivity: ActivityEvent[];
  allowance: { usedUsd: number | null; limitUsd: number | null; period: string | null; resetAt: string | null } | null;
}

export interface OperatorDashboard {
  usage: UsageSummary | null;
  series: UsagePoint[];
  topModels: ModelUsageRecord[];
  providers: ProviderRecord[];
  recentActivity: ActivityEvent[];
  guardrails: GuardrailSnapshot | null;
}

export interface CreateKeyInput {
  label: string;
  modelAccess: ModelAccess;
  spendCapUsd: number | null;
  spendPeriod: "day" | "week" | "month" | "lifetime" | null;
  rpmLimit: number | null;
}

export interface CreateKeyResult {
  key: ApiKeyRecord;
  secret: string;
}

export type UpdateKeyPolicyInput = CreateKeyInput;

export interface Page<T> {
  items: T[];
  nextCursor: string | null;
}

export interface PortalApi {
  getSession(): Promise<{ user: { displayName: string; email: string | null }; role: "operator" | "developer"; csrfToken: string }>;
  logout(): Promise<void>;
  localLogin(input: { username: string; password: string }): Promise<{ role: "operator" | "developer" }>;
  localSignup(input: { username: string; password: string; invite: string }): Promise<{ role: "operator" | "developer" }>;
  getDeveloperDashboard(): Promise<DeveloperDashboard>;
  getOperatorDashboard(): Promise<OperatorDashboard>;
  listKeys(): Promise<ApiKeyRecord[]>;
  createKey(input: CreateKeyInput): Promise<CreateKeyResult>;
  updateKeyPolicy(keyId: string, input: UpdateKeyPolicyInput): Promise<ApiKeyRecord>;
  revokeKey(keyId: string): Promise<void>;
  archiveKey(keyId: string): Promise<void>;
  listModels(): Promise<ModelRecord[]>;
  listActivity(cursor?: string): Promise<Page<ActivityEvent>>;
  listOperatorActivity(cursor?: string): Promise<Page<ActivityEvent>>;
  listPeople(): Promise<PersonRecord[]>;
  listProviders(): Promise<ProviderRecord[]>;
  listOperatorModels(): Promise<ModelRecord[]>;
  getGuardrails(): Promise<GuardrailSnapshot>;
  createProvider(input: CreateProviderInput): Promise<ProviderRecord>;
  syncProvider(providerId: string): Promise<{ providerId: string; modelsDiscovered: number; models: string[] }>;
  setModelPolicy(providerId: string, modelId: string, policy: ModelPolicyInput): Promise<void>;
  createInvite(input: { max_uses: number; expires_in_seconds: number }): Promise<CreateInviteResult>;
  listOperatorInvites(): Promise<InviteRecord[]>;
  revokeInvite(inviteId: string): Promise<InviteRecord>;
  getDeveloperInvites(): Promise<DeveloperInviteStatus>;
  createDeveloperInvite(): Promise<CreateInviteResult>;
  updatePersonPolicy(userId: string, input: { allowanceUsd: number | null; allowancePeriod: "day" | "week" | null; rpmLimit: number | null }): Promise<void>;
  setPersonEnabled(userId: string, enabled: boolean): Promise<void>;
  setGlobalStop(stopped: boolean): Promise<void>;
  updateGuardrails(input: { globalSpendCapUsd?: number; safetyReserveUsd?: number }): Promise<void>;
  blockIp(input: { ip: string; reason: string }): Promise<void>;
  unblockIp(ip: string): Promise<void>;
}
