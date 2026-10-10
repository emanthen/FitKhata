import { httpClient } from "./http-client";
import type { Page } from "./members";

export interface StaffRole {
  id: string;
  org: string;
  gym: string | null;
  user: string;
  role: string;
  is_active: boolean;
  created_at: string;
}

export const listStaffRoles = (): Promise<StaffRole[]> =>
  httpClient({ method: "GET", url: "/api/v1/staff-roles/" });

// --- Staff profiles (payroll) — FR-9.1 --------------------------------------

export type EmploymentType = "monthly" | "hourly";

export interface StaffProfile {
  id: string;
  user: string;
  full_name: string;
  employment_type: EmploymentType;
  base_salary_npr: string | null;
  hourly_rate_npr: string | null;
  pan_no: string | null; // owner-only; null for everyone else
  bank_name: string;
  bank_account: string | null; // owner-only; null for everyone else
  joined_on: string;
  badge_code: string;
  is_active: boolean;
}

export interface StaffProfileInput {
  user: string;
  employment_type: EmploymentType;
  base_salary_npr?: string;
  hourly_rate_npr?: string;
  pan_no?: string;
  bank_name?: string;
  bank_account_input?: string;
  joined_on: string;
}

export const listStaffProfiles = (): Promise<StaffProfile[] | Page<StaffProfile>> =>
  httpClient({ method: "GET", url: "/api/v1/staff-profiles/" });

export const createStaffProfile = (data: StaffProfileInput): Promise<StaffProfile> =>
  httpClient({ method: "POST", url: "/api/v1/staff-profiles/", data });

export const updateStaffProfile = (
  id: string,
  data: Partial<StaffProfileInput>
): Promise<StaffProfile> => httpClient({ method: "PATCH", url: `/api/v1/staff-profiles/${id}/`, data });

// --- Roster — FR-9.2 ---------------------------------------------------------

export interface ShiftTemplate {
  id: string;
  weekday: number; // 0=Monday .. 6=Sunday
  start: string;
  end: string;
  role: string;
}

export const listShiftTemplates = (): Promise<ShiftTemplate[] | Page<ShiftTemplate>> =>
  httpClient({ method: "GET", url: "/api/v1/staff-shift-templates/" });

export const createShiftTemplate = (
  data: Omit<ShiftTemplate, "id">
): Promise<ShiftTemplate> => httpClient({ method: "POST", url: "/api/v1/staff-shift-templates/", data });

export interface StaffShift {
  id: string;
  staff: string;
  date: string;
  start: string;
  end: string;
  template: string | null;
}

export interface ShiftConflictError {
  detail: string;
  conflicting_shift_id: string;
}

export const listStaffShifts = (): Promise<StaffShift[] | Page<StaffShift>> =>
  httpClient({ method: "GET", url: "/api/v1/staff-shifts/" });

export const createStaffShift = (data: {
  staff: string;
  date: string;
  start: string;
  end: string;
  template?: string;
}): Promise<StaffShift> => httpClient({ method: "POST", url: "/api/v1/staff-shifts/", data });

// --- Staff attendance — FR-9.3 -----------------------------------------------

export interface StaffAttendance {
  id: string;
  staff: string;
  clock_in: string;
  clock_out: string | null;
  source: "qr" | "biometric" | "manual";
}

export const listStaffAttendances = (): Promise<StaffAttendance[] | Page<StaffAttendance>> =>
  httpClient({ method: "GET", url: "/api/v1/staff-attendances/" });

// --- Leave — FR-9.4 -----------------------------------------------------------

export type LeaveKind = "sick" | "casual" | "festival" | "unpaid" | "other";
export type LeaveStatus = "pending" | "approved" | "rejected";

export interface LeaveRequest {
  id: string;
  staff: string;
  from_date: string;
  to_date: string;
  kind: LeaveKind;
  reason: string;
  status: LeaveStatus;
  reviewed_by: string | null;
  reviewed_at: string | null;
}

export const listLeaveRequests = (status?: LeaveStatus): Promise<LeaveRequest[] | Page<LeaveRequest>> =>
  httpClient({
    method: "GET",
    url: "/api/v1/leave-requests/",
    params: status ? { status } : undefined,
  });

export const submitLeaveRequest = (data: {
  staff: string;
  from_date: string;
  to_date: string;
  kind: LeaveKind;
  reason?: string;
}): Promise<LeaveRequest> => httpClient({ method: "POST", url: "/api/v1/leave-requests/", data });

export const approveLeaveRequest = (id: string): Promise<LeaveRequest> =>
  httpClient({ method: "POST", url: `/api/v1/leave-requests/${id}/approve/` });

export const rejectLeaveRequest = (id: string): Promise<LeaveRequest> =>
  httpClient({ method: "POST", url: `/api/v1/leave-requests/${id}/reject/` });

export interface LeaveBalance {
  id: string;
  staff: string;
  kind: LeaveKind;
  days_available: string;
}

export const listLeaveBalances = (): Promise<LeaveBalance[] | Page<LeaveBalance>> =>
  httpClient({ method: "GET", url: "/api/v1/leave-balances/" });

export const adjustLeaveBalance = (data: {
  staff: string;
  kind: LeaveKind;
  delta_days: string;
}): Promise<LeaveBalance> =>
  httpClient({ method: "POST", url: "/api/v1/leave-balances/adjust/", data });

// --- Advances — FR-9.5 --------------------------------------------------------

export interface Advance {
  id: string;
  staff: string;
  amount_npr: string;
  date: string;
  recovered_in_run: string | null;
}

export const listAdvances = (): Promise<Advance[] | Page<Advance>> =>
  httpClient({ method: "GET", url: "/api/v1/advances/" });

export const createAdvance = (data: {
  staff: string;
  amount_npr: string;
  date: string;
}): Promise<Advance> => httpClient({ method: "POST", url: "/api/v1/advances/", data });

// --- Payroll — FR-9.6 ----------------------------------------------------------

export type PayrollRunStatus = "draft" | "review" | "finalized";

export interface Payslip {
  id: string;
  run: string;
  staff: string;
  base_npr: string;
  commission_npr: string;
  incentives_npr: string;
  advances_npr: string;
  tds_npr: string;
  social_security_npr: string;
  net_npr: string;
}

export interface PayrollRun {
  id: string;
  period_bs: string;
  status: PayrollRunStatus;
  totals_npr: string;
  finalized_by: string | null;
  finalized_at: string | null;
  payslips: Payslip[];
}

export const listPayrollRuns = (): Promise<PayrollRun[] | Page<PayrollRun>> =>
  httpClient({ method: "GET", url: "/api/v1/payroll-runs/" });

export const getPayrollRun = (id: string): Promise<PayrollRun> =>
  httpClient({ method: "GET", url: `/api/v1/payroll-runs/${id}/` });

export const createPayrollRun = (period_bs: string): Promise<PayrollRun> =>
  httpClient({ method: "POST", url: "/api/v1/payroll-runs/", data: { period_bs } });

export const finalizePayrollRun = (id: string): Promise<PayrollRun> =>
  httpClient({ method: "POST", url: `/api/v1/payroll-runs/${id}/finalize/` });

export const listPayslips = (runId?: string): Promise<Payslip[] | Page<Payslip>> =>
  httpClient({
    method: "GET",
    url: "/api/v1/payslips/",
    params: runId ? { run: runId } : undefined,
  });

export const setPayslipIncentives = (id: string, incentives_npr: string): Promise<Payslip> =>
  httpClient({
    method: "POST",
    url: `/api/v1/payslips/${id}/set_incentives/`,
    data: { incentives_npr },
  });

export const fetchPayslipPdf = (id: string, lang: "en" | "ne" = "en"): Promise<Blob> =>
  httpClient({
    method: "GET",
    url: `/api/v1/payslips/${id}/pdf`,
    params: { lang },
    responseType: "blob",
  });

export const confirmTaxSlabs = (fiscalYear: string): Promise<Record<string, unknown>> =>
  httpClient({ method: "POST", url: `/api/v1/staff/tax/slabs/${fiscalYear}/confirm` });

// --- Leaderboard — FR-9.7 -------------------------------------------------

export interface LeaderboardRow {
  staff_id: string;
  badge_code: string;
  full_name: string;
  renewals_sold: number;
  renewals_npr: string;
  calls_completed: number;
  saves: number;
}

export const getStaffLeaderboard = (periodBs: string): Promise<LeaderboardRow[]> =>
  httpClient({
    method: "GET",
    url: "/api/v1/staff/leaderboard",
    params: { period_bs: periodBs },
  });

// --- Checklists — FR-9.8 -------------------------------------------------------

export interface ShiftChecklist {
  id: string;
  name: string;
  items: string[];
}

export const listShiftChecklists = (): Promise<ShiftChecklist[] | Page<ShiftChecklist>> =>
  httpClient({ method: "GET", url: "/api/v1/shift-checklists/" });

export const createShiftChecklist = (data: {
  name: string;
  items: string[];
}): Promise<ShiftChecklist> =>
  httpClient({ method: "POST", url: "/api/v1/shift-checklists/", data });

export interface ChecklistCompletion {
  id: string;
  checklist: string;
  date: string;
  completed_by: string | null;
  checked_items: string[];
  completed_at: string;
}

export const listChecklistCompletions = (): Promise<
  ChecklistCompletion[] | Page<ChecklistCompletion>
> => httpClient({ method: "GET", url: "/api/v1/checklist-completions/" });

export const submitChecklistCompletion = (data: {
  checklist: string;
  date: string;
  checked_items: string[];
}): Promise<ChecklistCompletion> =>
  httpClient({ method: "POST", url: "/api/v1/checklist-completions/submit/", data });
