import { httpClient } from "./http-client";

// --- Subscription / feature gating — FR-11.2 --------------------------------

export interface Subscription {
  plan_code: "starter" | "pro" | "enterprise";
  status: "trial" | "active" | "grace" | "read_only" | "suspended" | "cancelled";
  billing_cycle: "monthly" | "annual";
  branches: number;
  current_period_end: string;
  member_limit: number | null;
  member_count: number;
  features: Record<string, boolean>;
}

export const getMySubscription = (): Promise<Subscription> =>
  httpClient({ method: "GET", url: "/api/v1/saas/subscription" });

// --- SaaS invoices — FR-11.3 --------------------------------------------------

export interface SaasInvoice {
  id: number;
  number: string;
  kind: "subscription" | "sms_topup";
  period: string | null;
  total_npr: string;
  status: "draft" | "issued" | "paid" | "void";
  paid_via: string;
  created_at: string;
}

export const listSaasInvoices = (): Promise<SaasInvoice[]> =>
  httpClient({ method: "GET", url: "/api/v1/saas/invoices" });

export interface GatewayRedirect {
  url: string;
  method: "GET" | "POST";
  fields: Record<string, string>;
}

export const paySaasInvoice = (
  invoiceId: number,
  provider: "esewa" | "khalti" | "fonepay",
  returnUrl: string
): Promise<{ invoice_id: number; redirect: GatewayRedirect }> =>
  httpClient({
    method: "POST",
    url: `/api/v1/saas/invoices/${invoiceId}/pay`,
    data: { provider, return_url: returnUrl },
  });

export const confirmSaasInvoicePayment = (
  invoiceId: number,
  provider: string,
  callbackData: Record<string, string>
): Promise<{ status: string }> =>
  httpClient({
    method: "POST",
    url: `/api/v1/saas/invoices/${invoiceId}/callback`,
    data: { provider, ...callbackData },
  });

// --- SMS wallet top-up — FR-11.5 ----------------------------------------------

export const topupSmsWallet = (
  amountNpr: string,
  provider: "esewa" | "khalti" | "fonepay",
  returnUrl: string
): Promise<{ invoice_id: number; redirect: GatewayRedirect }> =>
  httpClient({
    method: "POST",
    url: "/api/v1/saas/sms-wallet/topup",
    data: { amount_npr: amountNpr, provider, return_url: returnUrl },
  });

// --- Support tickets — FR-11.6 -------------------------------------------------

export interface SupportTicket {
  id: number;
  subject: string;
  priority: "low" | "medium" | "high" | "urgent";
  status: "open" | "pending" | "resolved";
  created_at: string;
  updated_at: string;
}

export const listSupportTickets = (): Promise<SupportTicket[]> =>
  httpClient({ method: "GET", url: "/api/v1/saas/support-tickets" });

export const createSupportTicket = (data: {
  subject: string;
  priority?: string;
  message?: string;
}): Promise<{ id: number }> =>
  httpClient({ method: "POST", url: "/api/v1/saas/support-tickets", data });

export const addSupportTicketMessage = (ticketId: number, body: string): Promise<void> =>
  httpClient({
    method: "POST",
    url: `/api/v1/saas/support-tickets/${ticketId}/messages`,
    data: { body },
  });

// --- Data export & account deletion — FR-11.7 ----------------------------------

export const exportMyData = (): Promise<{ status: string }> =>
  httpClient({ method: "POST", url: "/api/v1/saas/export-data" });

export const deleteMyAccount = (): Promise<{ status: string }> =>
  httpClient({ method: "POST", url: "/api/v1/saas/delete-account" });
