import { httpClient } from "./http-client";

export type RetentionCallOutcome =
  | "reached"
  | "no_answer"
  | "coming_back"
  | "injured"
  | "quitting"
  | "call_back";

export interface RetentionCall {
  id: string;
  member: string;
  member_name: string;
  member_phone: string;
  queue_date: string;
  assigned_to: string | null;
  outcome: RetentionCallOutcome | "";
  call_back_on: string | null;
  notes: string;
  completed_at: string | null;
  created_at: string;
}

export const listCallQueue = (queueDate?: string): Promise<RetentionCall[]> =>
  httpClient({
    method: "GET",
    url: "/api/v1/retention/calls/",
    params: queueDate ? { queue_date: queueDate } : {},
  });

export interface CompleteCallInput {
  outcome: RetentionCallOutcome;
  call_back_on?: string;
  notes?: string;
}

export const completeCall = (id: string, data: CompleteCallInput): Promise<RetentionCall> =>
  httpClient({ method: "POST", url: `/api/v1/retention/calls/${id}/complete/`, data });

// --- Freezes -----------------------------------------------------------

export type FreezeReason = "dashain" | "tihar" | "chhath" | "travel" | "injury" | "other";

export interface MembershipFreeze {
  id: string;
  membership: string;
  member_name: string;
  batch_id: string;
  reason: FreezeReason;
  start_date: string;
  end_date: string;
  days: number;
  previous_expiry: string;
  fee_npr: string;
  reverted_at: string | null;
  created_at: string;
}

export interface FreezePreviewRow {
  member_id: string;
  member_name: string;
  membership_id: string;
  previous_expiry: string;
  new_expiry: string;
  would_exceed_max: boolean;
}

export const previewFreeze = (
  start_date: string,
  end_date: string,
  reason: FreezeReason
): Promise<{ count: number; rows: FreezePreviewRow[] }> =>
  httpClient({
    method: "POST",
    url: "/api/v1/retention/freezes/preview",
    data: { start_date, end_date, reason },
  });

export const confirmBulkFreeze = (
  start_date: string,
  end_date: string,
  reason: FreezeReason
): Promise<{ batch_id: string }> =>
  httpClient({
    method: "POST",
    url: "/api/v1/retention/freezes/bulk",
    data: { start_date, end_date, reason },
  });

export const individualFreeze = (data: {
  membership_id: string;
  start_date: string;
  end_date: string;
  reason: FreezeReason;
  fee_npr?: string;
}): Promise<MembershipFreeze> =>
  httpClient({ method: "POST", url: "/api/v1/retention/freezes/individual", data });

export const revertFreezeBatch = (batchId: string): Promise<{ reverted: number }> =>
  httpClient({
    method: "POST",
    url: `/api/v1/retention/freezes/batches/${batchId}/revert`,
  });

export const listFreezeHistory = (): Promise<MembershipFreeze[]> =>
  httpClient({ method: "GET", url: "/api/v1/retention/freezes/" });

// --- Member-initiated freeze requests (FR-8.6) --------------------------

export type FreezeRequestStatus = "pending" | "approved" | "rejected";

export interface FreezeRequest {
  id: string;
  member: string;
  member_name: string;
  membership: string;
  start_date: string;
  end_date: string;
  reason: string;
  status: FreezeRequestStatus;
  reviewed_by: string | null;
  reviewed_at: string | null;
  created_at: string;
}

export const submitMemberFreezeRequest = (
  passToken: string,
  data: { start_date: string; end_date: string; reason: string }
): Promise<FreezeRequest> =>
  httpClient({ method: "POST", url: `/api/v1/m/pass/${passToken}/freeze-requests`, data });

export const listFreezeRequests = (status?: FreezeRequestStatus): Promise<FreezeRequest[]> =>
  httpClient({
    method: "GET",
    url: "/api/v1/retention/freeze-requests/",
    params: status ? { status } : undefined,
  });

export const approveFreezeRequest = (id: string): Promise<FreezeRequest> =>
  httpClient({ method: "POST", url: `/api/v1/retention/freeze-requests/${id}/approve/` });

export const rejectFreezeRequest = (id: string): Promise<FreezeRequest> =>
  httpClient({ method: "POST", url: `/api/v1/retention/freeze-requests/${id}/reject/` });

// --- Campaigns -----------------------------------------------------------

export type CampaignKind = "winback_30" | "winback_60" | "winback_90";

export interface Campaign {
  id: string;
  kind: CampaignKind;
  promo: string | null;
  sent_count: number;
  converted_count: number;
  created_at: string;
}

export const listCampaigns = (): Promise<Campaign[]> =>
  httpClient({ method: "GET", url: "/api/v1/retention/campaigns/" });

export const sendCampaign = (kind: CampaignKind, promo_code?: string): Promise<Campaign> =>
  httpClient({ method: "POST", url: "/api/v1/retention/campaigns/", data: { kind, promo_code } });

export const recomputeCampaign = (id: string): Promise<Campaign> =>
  httpClient({ method: "POST", url: `/api/v1/retention/campaigns/${id}/recompute/` });

// --- Dashboard -----------------------------------------------------------

export interface RetentionDashboard {
  churn_rate: number;
  saves_this_month: number;
  revenue_protected_npr: string;
}

export const getRetentionDashboard = (): Promise<RetentionDashboard> =>
  httpClient({ method: "GET", url: "/api/v1/retention/dashboard" });
