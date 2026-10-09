import { httpClient } from "./http-client";

export interface Member {
  id: string;
  member_code: string;
  full_name: string;
  phone: string;
  gender: string;
  dob: string | null;
  emergency_contact: Record<string, unknown>;
  photo: string | null;
  tags: string[];
  status: string;
  risk_state: string;
  churn_score: number;
  last_check_in_at: string | null;
  marketing_opt_in: boolean;
  referred_by: string | null;
  created_at: string;
}

export interface Plan {
  id: string;
  name: string;
  duration_days: number;
  price_npr: string;
  joining_fee_npr: string;
  access_hours: Record<string, unknown>;
  pt_sessions: number;
  max_freeze_days: number;
  is_active: boolean;
}

export interface AddOn {
  id: string;
  name: string;
  price_npr: string;
  kind: "locker" | "towel" | "pt" | "diet";
}

export interface PromoCode {
  id: string;
  code: string;
  kind: "flat" | "percent";
  value: string;
  valid_from: string;
  valid_to: string;
  usage_limit: number | null;
  per_member_once: boolean;
  times_used: number;
}

export interface Membership {
  id: string;
  member: string;
  plan: string;
  start_date: string;
  expiry_date: string;
  status: string;
  invoice: string | null;
  created_at: string;
}

export interface ImportJob {
  id: string;
  status: "pending" | "running" | "done" | "failed";
  total_rows: number;
  success_count: number;
  error_report: string | null;
  created_at: string;
}

export interface Page<T> {
  results: T[];
  next: string | null;
  previous: string | null;
}

export interface MemberListParams {
  q?: string;
  status?: string;
  risk_state?: string;
  tag?: string;
  plan?: string;
  cursor?: string;
}

export const listMembers = (params: MemberListParams = {}): Promise<Page<Member> | Member[]> =>
  httpClient({ method: "GET", url: "/api/v1/members/", params });

export const getMember = (id: string): Promise<Member> =>
  httpClient({ method: "GET", url: `/api/v1/members/${id}/` });

export interface RegisterMemberInput {
  full_name: string;
  phone: string;
  gender?: string;
  dob?: string;
  emergency_contact?: Record<string, unknown>;
  tags?: string[];
  marketing_opt_in?: boolean;
  photo?: File;
  referred_by?: string;
}

export const registerMember = (data: RegisterMemberInput): Promise<Member> => {
  if (!data.photo) {
    return httpClient({ method: "POST", url: "/api/v1/members/", data });
  }
  const form = new FormData();
  for (const [key, value] of Object.entries(data)) {
    if (value === undefined) continue;
    if (key === "tags" || key === "emergency_contact") {
      form.append(key, JSON.stringify(value));
    } else {
      form.append(key, value as string | Blob);
    }
  }
  // No explicit Content-Type: axios sets multipart/form-data with the
  // required boundary param itself when it sees a FormData body — setting
  // it manually here would omit the boundary and break server-side parsing.
  return httpClient({ method: "POST", url: "/api/v1/members/", data: form });
};

export const sellMembership = (
  memberId: string,
  data: { plan_id: string; promo_code?: string; addon_ids?: string[] }
): Promise<Membership> =>
  httpClient({ method: "POST", url: `/api/v1/members/${memberId}/sell/`, data });

export const transferMember = (memberId: string, gymId: string): Promise<Member> =>
  httpClient({
    method: "POST",
    url: `/api/v1/members/${memberId}/transfer/`,
    data: { gym_id: gymId },
  });

export const listMemberships = (memberId: string): Promise<Membership[] | Page<Membership>> =>
  httpClient({ method: "GET", url: "/api/v1/memberships/", params: { member: memberId } });

export const listPlans = (): Promise<Plan[]> =>
  httpClient({ method: "GET", url: "/api/v1/plans/" });

export const createPlan = (data: Omit<Plan, "id">): Promise<Plan> =>
  httpClient({ method: "POST", url: "/api/v1/plans/", data });

export const listAddOns = (): Promise<AddOn[]> =>
  httpClient({ method: "GET", url: "/api/v1/addons/" });

export const createAddOn = (data: Omit<AddOn, "id">): Promise<AddOn> =>
  httpClient({ method: "POST", url: "/api/v1/addons/", data });

export const listPromoCodes = (): Promise<PromoCode[]> =>
  httpClient({ method: "GET", url: "/api/v1/promo-codes/" });

export const createPromoCode = (
  data: Omit<PromoCode, "id" | "times_used">
): Promise<PromoCode> => httpClient({ method: "POST", url: "/api/v1/promo-codes/", data });

export const importMembers = (file: File): Promise<ImportJob> => {
  const form = new FormData();
  form.append("file", file);
  return httpClient({ method: "POST", url: "/api/v1/members/import", data: form });
};

export const getImportJobStatus = (jobId: string): Promise<ImportJob> =>
  httpClient({ method: "GET", url: `/api/v1/members/import/${jobId}` });

export interface Waiver {
  id: string;
  member: string;
  signed_pdf: string;
  signed_at: string;
}

export const uploadWaiver = (memberId: string, file: File | Blob): Promise<Waiver> => {
  const form = new FormData();
  form.append("member", memberId);
  form.append("signed_pdf", file, "waiver.png");
  return httpClient({ method: "POST", url: "/api/v1/waivers/", data: form });
};

// --- Member-facing membership status (FR-8.3 home status card) ----------

export interface MemberMembershipStatus {
  plan_name: string;
  expiry_date: string;
  days_left: number;
  status: string;
}

export const getMemberMembershipStatus = (
  passToken: string
): Promise<MemberMembershipStatus | null> =>
  httpClient({ method: "GET", url: `/api/v1/m/pass/${passToken}/membership-status` });

// --- Member-facing feedback/complaint form (FR-8.6) ---------------------

export interface MemberFeedback {
  id: string;
  member: string;
  message: string;
  created_at: string;
}

export const submitMemberFeedback = (
  passToken: string,
  message: string
): Promise<MemberFeedback> =>
  httpClient({
    method: "POST",
    url: `/api/v1/m/pass/${passToken}/feedback`,
    data: { message },
  });
