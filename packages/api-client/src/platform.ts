import { httpClient } from "./http-client";

// FitKhata-staff-only endpoints (saas.permissions.IsPlatformStaff) — kept
// in its own module, separate from saas.ts's tenant-facing functions, so
// the two audiences aren't visually conflated in one file.

export interface TenantRow {
  org_id: string;
  org_name: string;
  plan_code: string;
  status: string;
  mrr_npr: string;
  member_count: number;
  last_active_at: string | null;
  health_score: number;
}

export const listTenants = (): Promise<TenantRow[]> =>
  httpClient({ method: "GET", url: "/api/v1/platform/tenants" });

export interface PlatformMetrics {
  mrr_npr: string;
  churn_rate_pct: number;
  trial_conversion_pct: number;
  by_status: Record<string, number>;
}

export const getPlatformMetrics = (): Promise<PlatformMetrics> =>
  httpClient({ method: "GET", url: "/api/v1/platform/metrics" });

export const impersonate = (
  orgId: string,
  reason: string
): Promise<{ access: string; org_id: string; expires_in: number }> =>
  httpClient({
    method: "POST",
    url: "/api/v1/platform/impersonate",
    data: { org_id: orgId, reason },
  });

export interface FeatureFlag {
  id: number;
  key: string;
  default: boolean;
  per_org_overrides: Record<string, boolean>;
  rollout_pct: number | null;
}

export const listFeatureFlags = (): Promise<FeatureFlag[]> =>
  httpClient({ method: "GET", url: "/api/v1/platform/feature-flags" });

export const upsertFeatureFlag = (data: {
  key: string;
  default?: boolean;
  rollout_pct?: number | null;
  per_org_overrides?: Record<string, boolean>;
}): Promise<{ id: number }> =>
  httpClient({ method: "POST", url: "/api/v1/platform/feature-flags", data });

export const broadcastAnnouncement = (
  subject: string,
  body: string
): Promise<{ sent: number }> =>
  httpClient({
    method: "POST",
    url: "/api/v1/platform/announcements",
    data: { subject, body },
  });

export interface PlatformTicketRow {
  id: number;
  org__name: string;
  subject: string;
  priority: string;
  status: string;
  created_at: string;
  updated_at: string;
}

export const listAllTickets = (): Promise<PlatformTicketRow[]> =>
  httpClient({ method: "GET", url: "/api/v1/platform/tickets" });

export const markSaasInvoicePaidByBank = (invoiceId: number): Promise<{ status: string }> =>
  httpClient({
    method: "POST",
    url: `/api/v1/platform/saas-invoices/${invoiceId}/mark-paid-bank`,
  });

// --- Leads — FR-12.6 (flat capture log, no pipeline UI exists for this to
// hook into — see saas.models.Lead's own docstring) ------------------------

export interface LeadRow {
  id: number;
  full_name: string;
  phone: string;
  email: string;
  source: string;
  status: "new" | "contacted" | "converted" | "lost";
  created_at: string;
}

export const listLeads = (): Promise<LeadRow[]> =>
  httpClient({ method: "GET", url: "/api/v1/platform/leads" });
