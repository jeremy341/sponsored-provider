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
  estimatedSpendUsd: string | null;
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
  estimated_spend_usd: string | null;
}

export interface AnalyticsUsagePoint {
  day: string;
  requests: number;
  totalTokens: number | null;
  estimatedSpendUsd: string | null;
  unpricedRequests: number;
}

export interface ModelUsageRecord {
  modelId: string;
  providerName: string;
  requests: number;
  totalTokens: number | null;
  estimatedSpendUsd: string | null;
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
  estimatedCostUsd: string | null;
  costSource: "gateway_estimate" | "provider_reported" | "unknown";
  requestId?: string | null;
  tokenCompleteness?: "complete" | "partial" | "unknown";
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
  spendCapUsd: string | null;
  spendUsedUsd: string | null;
  spendPeriod: "day" | "week" | "month" | "lifetime" | null;
  spendResetAt: string | null;
  rpmLimit: number | null;
  createdAt: string;
  lastUsedAt: string | null;
  status: "active" | "disabled" | "archived";
}

export interface ModelRecord {
  id: string;
  displayName?: string;
  upstreamModelId?: string;
  providerId?: string;
  providerName: string;
  capabilities: Array<"text" | "vision">;
  inputUsdPerMillion: string | null;
  outputUsdPerMillion: string | null;
  cacheUsdPerMillion: string | null;
  pricingVerified: boolean;
  priceSource?: string | null;
  approved: boolean;
  available: boolean;
  syncedAt: string | null;
  activeRouteCount: number | null;
}

export type DashboardRange = "current_month" | "7d" | "30d" | "90d";

export interface ModelSpendRecord {
  id: string;
  modelId: string;
  providerName: string;
  requests: number;
  totalTokens: number | null;
  spendUsd: string | null;
}

export interface AnalyticsPeriod {
  key: DashboardRange;
  from: string;
  to: string;
  timezone: "Europe/Berlin";
}

export interface DashboardAnalytics {
  period: AnalyticsPeriod;
  summary: UsageSummary | null;
  series: AnalyticsUsagePoint[];
  topModels: ModelUsageRecord[];
  modelSpend: ModelSpendRecord[];
  knownSpendUsd: string | null;
  unpricedRequests: number;
}

export interface PersonRecord {
  id: string;
  displayName: string;
  email: string | null;
  status: "active" | "pending" | "disabled";
  allowanceUsd: string | null;
  allowancePeriod: "daily" | "weekly" | "monthly" | null;
  rpmLimit: number | null;
  usedUsd: string | null;
  reservedUsd: string;
  allowanceResetAt: string | null;
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

export interface ProviderBudgetRecord {
  limitUsd: string | null;
  period: string | null;
  reserveUsd: string;
  usedUsd: string | null;
  reservedUsd: string;
  remainingUsd: string | null;
  resetAt: string | null;
}

export interface ProviderConnectionRecord {
  id: string;
  brandId: string | null;
  brandSlug: string | null;
  brandName: string;
  connectionLabel: string;
  providerKind: string;
  baseUrlDisplay: string;
  enabled: boolean;
  mappingStatus: string;
  health: "healthy" | "degraded" | "unknown" | "disabled" | "error";
  lastSyncAt: string | null;
  discoveredModels: number;
  approvedModels: number;
  budget: ProviderBudgetRecord;
}

export interface ProviderBrandRecord {
  id: string;
  slug: string;
  name: string;
  connections: ProviderConnectionRecord[];
}

export interface PriceVersionRecord {
  id?: string;
  inputUsdPerMillion: string;
  outputUsdPerMillion: string;
  cachedInputUsdPerMillion: string | null;
  source: string | null;
  effectiveAt?: string | null;
  sourceUrl?: string | null;
  evidence?: string | null;
  confidence?: string | null;
}

export interface OfferRouteRecord {
  id: string;
  connectionId: string;
  connectionLabel: string;
  upstreamModelId: string;
  order: number;
  enabled: boolean;
  active: boolean;
  connectionEnabled: boolean;
  stale: boolean;
  reviewRequired: boolean;
  priceStatus: string;
  mismatchReason?: string | null;
}

export interface CatalogOfferRecord {
  id: string;
  brandSlug: string;
  brandName: string;
  canonicalModelId: string;
  displayName: string;
  capabilities: string[];
  approved: boolean;
  available: boolean;
  activePrice: PriceVersionRecord | null;
  pendingPrice: PriceVersionRecord | null;
  priceSuggestions: PriceVersionRecord[];
  routes: OfferRouteRecord[];
}

export interface OperatorUsageFilter {
  cursor?: string | null;
  limit?: number;
  brandSlug?: string;
  connectionId?: string;
  model?: string;
  from?: string;
  to?: string;
  outcome?: string;
}

export interface DeveloperActivityFilter {
  cursor?: string;
  limit?: number;
  keyId?: string;
  model?: string;
  from?: string;
  to?: string;
  outcome?: string;
}

export interface OperatorActivityRecord extends ActivityEvent {
  brandSlug?: string | null;
  connectionId?: string | null;
  connectionLabel?: string | null;
}

export type CreateProviderResponse =
  | { id: string; name: string; brandSlug: string; connectionLabel: string; models: string[] }
  | { provider: ProviderConnectionRecord; sync: { tested: boolean; discovered: number; models: string[]; error: string | null } };

export type SyncProviderResponse =
  | { providerId: string; connectionId: string; modelsDiscovered: number; models: string[]; staleModels: number }
  | { providerId: string; tested: boolean; discovered: number; models: string[]; error: string | null };

export interface CreateProviderInput {
  name: string;
  brandSlug: string;
  connectionLabel: string;
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
  allowance: {
    usedUsd: string;
    reservedUsd: string;
    consumedUsd: string;
    limitUsd: string | null;
    remainingUsd: string | null;
    period: string | null;
    resetAt: string | null;
    source: string;
    usedNanoUsd?: number;
    reservedNanoUsd?: number;
    limitNanoUsd?: number | null;
  } | null;
  analytics?: DashboardAnalytics;
}

export interface OperatorDashboard {
  usage: UsageSummary | null;
  series: UsagePoint[];
  topModels: ModelUsageRecord[];
  providers: ProviderRecord[];
  recentActivity: ActivityEvent[];
  guardrails: GuardrailSnapshot | null;
  analytics?: DashboardAnalytics;
}

export interface CreateKeyInput {
  label: string;
  modelAccess: ModelAccess;
  spendCapUsd: string | null;
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
  getDeveloperDashboard(range?: DashboardRange): Promise<DeveloperDashboard>;
  getOperatorDashboard(range?: DashboardRange): Promise<OperatorDashboard>;
  listKeys(): Promise<ApiKeyRecord[]>;
  createKey(input: CreateKeyInput): Promise<CreateKeyResult>;
  updateKeyPolicy(keyId: string, input: UpdateKeyPolicyInput): Promise<ApiKeyRecord>;
  revokeKey(keyId: string): Promise<void>;
  archiveKey(keyId: string): Promise<void>;
  listModels(): Promise<ModelRecord[]>;
  listActivity(filters?: DeveloperActivityFilter): Promise<Page<ActivityEvent>>;
  listOperatorActivity(filters?: OperatorUsageFilter): Promise<Page<OperatorActivityRecord>>;
  listPeople(): Promise<PersonRecord[]>;
  listProviders(): Promise<ProviderConnectionRecord[]>;
  listOperatorOffers(): Promise<CatalogOfferRecord[]>;
  listOperatorModels(): Promise<ModelRecord[]>;
  getGuardrails(): Promise<GuardrailSnapshot>;
  createProvider(input: CreateProviderInput): Promise<CreateProviderResponse>;
  syncProvider(providerId: string): Promise<SyncProviderResponse>;
  updateOfferPrice(offerId: string, input: PriceVersionRecord): Promise<{ id: string; offerId: string; status: string }>;
  approveOfferPrice(offerId: string, versionId: string): Promise<void>;
  setOfferAvailable(offerId: string, available: boolean): Promise<void>;
  setRouteAvailability(routeId: string, enabled: boolean): Promise<void>;
  updateRouteOrder(offerId: string, connectionIds: string[]): Promise<void>;
  mapConnectionModel(connectionId: string, upstreamModelId: string, offerId: string): Promise<void>;
  updateConnectionBudget(connectionId: string, input: { limitUsd: string | null; period: string | null; reserveUsd: string }): Promise<void>;
  setModelPolicy(providerId: string, modelId: string, policy: ModelPolicyInput): Promise<void>;
  createInvite(input: { max_uses: number; expires_in_seconds: number }): Promise<CreateInviteResult>;
  listOperatorInvites(): Promise<InviteRecord[]>;
  revokeInvite(inviteId: string): Promise<InviteRecord>;
  getDeveloperInvites(): Promise<DeveloperInviteStatus>;
  createDeveloperInvite(): Promise<CreateInviteResult>;
  updatePersonPolicy(userId: string, input: { allowanceUsd: string | null; allowancePeriod: "daily" | "weekly" | "monthly" | null; rpmLimit: number | null }): Promise<void>;
  setPersonEnabled(userId: string, enabled: boolean): Promise<void>;
  setGlobalStop(stopped: boolean): Promise<void>;
  updateGuardrails(input: { globalSpendCapUsd?: number; safetyReserveUsd?: number }): Promise<void>;
  blockIp(input: { ip: string; reason: string }): Promise<void>;
  unblockIp(ip: string): Promise<void>;
}

export interface DeveloperProviderStatus {
  provider: string;
  models: number;
  health: "healthy" | "degraded" | "unhealthy" | "unknown";
  sampleSize: number;
  successRate: number | null;
  p50LatencyMs: number | null;
  p95LatencyMs: number | null;
  lastActivityAt: string | null;
}

export interface OperatorSystemSnapshot {
  version: string;
  uptimeSeconds: number;
  pythonVersion: string;
  platform: string;
  inference: {
    stopped: boolean;
    stopSource: "emergency_stop" | "operator_stop" | null;
    globalSpendCapUsd: number | null;
    safetyReserveUsd: number | null;
  };
  jobs: {
    lastProviderSyncAt: string | null;
    backupStatus: string;
    lastBackupAt: string | null;
    lastRestoreTestAt: string | null;
  };
  database: {
    engine: string;
    sqliteVersion: string;
    path: string | null;
    sizeBytes: number;
    tableCount: number;
    schemaVersion: number;
  };
  counts: {
    users: number;
    activeApiKeys: number;
    providerConnections: number;
    activeOffers: number;
    usageEvents30d: number;
  };
}

export interface PlaygroundMessage {
  role: "user" | "assistant";
  content: string;
}

export interface PlaygroundTelemetry {
  status: "idle" | "running" | "success" | "error" | "stopped";
  model: string | null;
  provider: string | null;
  ttftMs: number | null;
  latencyMs: number | null;
  inputTokens: number | null;
  outputTokens: number | null;
  costUsd: number | null;
  costSource: "measured" | "estimate" | "settling" | null;
  error: string | null;
  errorCode: string | null;
}
