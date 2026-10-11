import { httpClient } from "./http-client";

// --- Dashboard — FR-10.1 -------------------------------------------------

export interface DashboardSummary {
  active_members: number;
  revenue_today_npr: string;
  revenue_month_npr: string;
  renewals_due: number;
  red_list_count: number;
}

export const getDashboardSummary = (): Promise<DashboardSummary> =>
  httpClient({ method: "GET", url: "/api/v1/reports/dashboard-summary" });

// --- Date-range charts — FR-10.1/10.2 ------------------------------------

export type ReportCalendar = "ad" | "bs";

export interface ReportRange {
  from: string;
  to: string;
  calendar?: ReportCalendar;
}

export interface RevenueTrendRow {
  day: string;
  amount_npr: string;
  payment_count: number;
}

export const getRevenueTrend = (range: ReportRange): Promise<RevenueTrendRow[]> =>
  httpClient({ method: "GET", url: "/api/v1/reports/revenue-trend", params: range });

export interface PlanMixRow {
  plan_id: string;
  amount_npr: string;
}

export const getPlanMix = (range: ReportRange): Promise<PlanMixRow[]> =>
  httpClient({ method: "GET", url: "/api/v1/reports/plan-mix", params: range });

export interface MembershipFlowRow {
  day: string;
  new_count: number;
  renewed_count: number;
  expired_count: number;
  churned_count: number;
}

export const getMembershipFlow = (range: ReportRange): Promise<MembershipFlowRow[]> =>
  httpClient({ method: "GET", url: "/api/v1/reports/membership-flow", params: range });

// --- Heatmaps — FR-10.3/10.4 ----------------------------------------------

export interface AttendanceHeatmapRow {
  weekday: number; // 0=Monday .. 6=Sunday
  hour: number;
  count: number;
}

export const getAttendanceHeatmap = (): Promise<AttendanceHeatmapRow[]> =>
  httpClient({ method: "GET", url: "/api/v1/reports/attendance-heatmap" });

export interface CohortRetentionRow {
  join_month: string;
  cohort_size: number;
  retained_m1: number;
  retained_m3: number;
  retained_m6: number;
  retained_m12: number;
}

export const getCohortRetention = (): Promise<CohortRetentionRow[]> =>
  httpClient({ method: "GET", url: "/api/v1/reports/cohort-retention" });

// --- Dues ageing — FR-10.6 -------------------------------------------------

export interface DuesAgeingBucket {
  count: number;
  total_npr: string;
}

export type DuesAgeing = Record<"0-30" | "31-60" | "60+", DuesAgeingBucket>;

export const getDuesAgeing = (): Promise<DuesAgeing> =>
  httpClient({ method: "GET", url: "/api/v1/reports/dues-ageing" });

export const fetchDuesAgeingExport = (format: "csv" | "xlsx"): Promise<Blob> =>
  httpClient({
    method: "GET",
    url: "/api/v1/reports/dues-ageing",
    // "export", not "format" — the latter is DRF's reserved content-
    // negotiation query param (see reports/views.py's DuesAgeingView).
    params: { export: format },
    responseType: "blob",
  });

// --- VAT sales register — FR-10.7 (owner-only) -----------------------------

export interface VatRegisterRow {
  bill_date_bs: string;
  number: string;
  buyer_name: string;
  buyer_pan: string;
  taxable_npr: string;
  vat_npr: string;
  total_npr: string;
}

export interface VatRegisterMonthlyTotal {
  taxable_npr: string;
  vat_npr: string;
  total_npr: string;
}

export interface VatRegister {
  rows: VatRegisterRow[];
  monthly_totals: Record<string, VatRegisterMonthlyTotal>;
}

export const getVatRegister = (fiscalYear: number): Promise<VatRegister> =>
  httpClient({
    method: "GET",
    url: "/api/v1/reports/vat-register",
    params: { fiscal_year: fiscalYear },
  });

export const fetchVatRegisterExport = (
  fiscalYear: number,
  format: "csv" | "xlsx" | "pdf"
): Promise<Blob> =>
  httpClient({
    method: "GET",
    url: "/api/v1/reports/vat-register",
    params: { fiscal_year: fiscalYear, export: format },
    responseType: "blob",
  });

// --- Accounting export — FR-12.5 (owner-only) ------------------------------

export type AccountingExportFormat = "tally" | "swastik";

export const fetchAccountingExport = (
  date: string,
  format: AccountingExportFormat
): Promise<Blob> =>
  httpClient({
    method: "GET",
    url: "/api/v1/reports/accounting-export",
    params: { date, format },
    responseType: "blob",
  });
