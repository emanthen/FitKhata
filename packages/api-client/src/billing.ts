import { httpClient } from "./http-client";
import type { AddOn, Page } from "./members";

export interface InvoiceLine {
  id: string;
  description: string;
  quantity: number;
  unit_price_npr: string;
  line_total_npr: string;
}

export type InvoiceStatus = "draft" | "issued" | "void";

export interface Invoice {
  id: string;
  number: string;
  fiscal_year: number;
  status: InvoiceStatus;
  member: string;
  subtotal_npr: string;
  discount_npr: string;
  taxable_npr: string;
  vat_npr: string;
  total_npr: string;
  bill_date: string | null;
  bill_date_bs: string;
  buyer_name: string;
  buyer_pan: string;
  void_reason: string;
  lines: InvoiceLine[];
  created_at: string;
}

export const listInvoices = (memberId: string): Promise<Invoice[] | Page<Invoice>> =>
  httpClient({ method: "GET", url: "/api/v1/invoices/", params: { member: memberId } });

export const voidInvoice = (invoiceId: string, reason: string): Promise<Invoice> =>
  httpClient({ method: "POST", url: `/api/v1/invoices/${invoiceId}/void/`, data: { reason } });

// --- Gateway credentials (IsOwner) ------------------------------------

export type GatewayProvider = "esewa" | "khalti" | "fonepay";
export type GatewayEnvironment = "sandbox" | "live";

export interface GatewayCredential {
  id: string;
  provider: GatewayProvider;
  environment: GatewayEnvironment;
  merchant_code: string;
  is_configured: boolean;
  is_active: boolean;
  created_at: string;
}

export interface GatewayCredentialInput {
  provider: GatewayProvider;
  environment: GatewayEnvironment;
  merchant_code: string;
  secret?: string;
  username?: string;
  password?: string;
  hmac_key?: string;
  is_active?: boolean;
}

export const listGatewayCredentials = (): Promise<GatewayCredential[] | Page<GatewayCredential>> =>
  httpClient({ method: "GET", url: "/api/v1/gateway-credentials/" });

export const createGatewayCredential = (
  data: GatewayCredentialInput
): Promise<GatewayCredential> =>
  httpClient({ method: "POST", url: "/api/v1/gateway-credentials/", data });

export const updateGatewayCredential = (
  id: string,
  data: Partial<GatewayCredentialInput>
): Promise<GatewayCredential> =>
  httpClient({ method: "PATCH", url: `/api/v1/gateway-credentials/${id}/`, data });

export const deleteGatewayCredential = (id: string): Promise<void> =>
  httpClient({ method: "DELETE", url: `/api/v1/gateway-credentials/${id}/` });

export const testGatewayConnection = (
  id: string
): Promise<{ ok: boolean; detail?: string }> =>
  httpClient({ method: "POST", url: `/api/v1/gateway-credentials/${id}/test-connection/` });

// --- Desk payment collection (FR-4.9) -----------------------------------

export type PaymentMode =
  | "esewa"
  | "khalti"
  | "fonepay"
  | "cash"
  | "manual_esewa"
  | "bank"
  | "cheque";

export interface Payment {
  id: string;
  member: string;
  invoice: string | null;
  shift: string | null;
  mode: PaymentMode;
  channel: "online" | "desk";
  transaction_uuid: string;
  gateway_ref: string;
  amount_npr: string;
  status: "pending" | "completed" | "failed" | "refunded";
  receipt_no: string;
  collected_by: string | null;
  created_at: string;
}

export const collectPayment = (data: {
  invoice_id: string;
  mode: "cash" | "manual_esewa" | "bank" | "cheque";
  amount_npr: string;
  shift_id?: string;
}): Promise<Payment> => httpClient({ method: "POST", url: "/api/v1/billing/payments", data });

export const generateFonepayQr = (data: {
  invoice_id: string;
  amount_npr: string;
}): Promise<{ payment_id: string; qr_message: string; websocket_url: string }> =>
  httpClient({ method: "POST", url: "/api/v1/billing/payments/fonepay/qr", data });

export const checkFonepayStatus = (paymentId: string): Promise<Payment> =>
  httpClient({
    method: "POST",
    url: `/api/v1/billing/payments/fonepay/${paymentId}/status`,
  });

// --- Cash shifts (FR-4.10) -----------------------------------------------

export interface CashShift {
  id: string;
  staff: string;
  opened_at: string;
  closed_at: string | null;
  opening_float_npr: string;
  counted_cash_npr: string | null;
  denominations: Record<string, number>;
  expected_cash_npr: string;
  variance_npr: string | null;
}

export const openCashShift = (openingFloatNpr: string): Promise<CashShift> =>
  httpClient({
    method: "POST",
    url: "/api/v1/billing/shifts",
    data: { opening_float_npr: openingFloatNpr },
  });

export const closeCashShift = (
  shiftId: string,
  data: { counted_cash_npr: string; denominations: Record<string, number> }
): Promise<CashShift> =>
  httpClient({ method: "POST", url: `/api/v1/billing/shifts/${shiftId}/close`, data });

// --- Settlement report (FR-4.11) ------------------------------------------

export interface SettlementReport {
  date: string;
  by_mode: Record<string, string>;
  total_npr: string;
}

export const getSettlementReport = (date?: string): Promise<SettlementReport> =>
  httpClient({
    method: "GET",
    url: "/api/v1/billing/settlement-report",
    params: date ? { date } : undefined,
  });

// --- Credit notes (FR-4.8) -------------------------------------------------

export interface CreditNote {
  id: string;
  invoice: string;
  amount_npr: string;
  reason: string;
  approved_by: string | null;
  approved_at: string | null;
  created_at: string;
}

export const listCreditNotes = (): Promise<CreditNote[] | Page<CreditNote>> =>
  httpClient({ method: "GET", url: "/api/v1/credit-notes/" });

export const createCreditNote = (data: {
  invoice: string;
  amount_npr: string;
  reason: string;
}): Promise<CreditNote> => httpClient({ method: "POST", url: "/api/v1/credit-notes/", data });

export const approveCreditNote = (id: string): Promise<CreditNote> =>
  httpClient({ method: "POST", url: `/api/v1/credit-notes/${id}/approve/` });

// --- Receipts --------------------------------------------------------------

export const fetchInvoicePdf = (invoiceId: string): Promise<Blob> =>
  httpClient({
    method: "GET",
    url: `/api/v1/billing/invoices/${invoiceId}/pdf`,
    responseType: "blob",
  });

export const fetchReceiptText = (invoiceId: string): Promise<{ text: string }> =>
  httpClient({ method: "GET", url: `/api/v1/billing/invoices/${invoiceId}/receipt-text` });

export const sendReceiptSms = (invoiceId: string): Promise<{ sent: boolean }> =>
  httpClient({ method: "POST", url: `/api/v1/billing/invoices/${invoiceId}/send-receipt-sms` });

// --- Member-facing online renewal (token-authenticated) --------------------

export interface RenewalRedirect {
  payment_id: string;
  redirect: {
    url: string;
    method: "GET" | "POST";
    fields: Record<string, string>;
  };
}

export interface RenewalPlan {
  id: string;
  name: string;
  duration_days: number;
  price_npr: string;
}

export const listRenewalPlans = (passToken: string): Promise<RenewalPlan[]> =>
  httpClient({ method: "GET", url: `/api/v1/m/pass/${passToken}/plans` });

export const listRenewalAddOns = (passToken: string): Promise<AddOn[]> =>
  httpClient({ method: "GET", url: `/api/v1/m/pass/${passToken}/addons` });

export type RenewalProvider = "esewa" | "khalti" | "fonepay";

export const initiateRenewal = (
  passToken: string,
  planId: string,
  provider: RenewalProvider,
  returnUrl: string,
  options?: { promoCode?: string; addonIds?: string[] }
): Promise<RenewalRedirect> =>
  httpClient({
    method: "POST",
    url: `/api/v1/m/pass/${passToken}/renew`,
    data: {
      plan_id: planId,
      provider,
      return_url: returnUrl,
      promo_code: options?.promoCode || undefined,
      addon_ids: options?.addonIds,
    },
  });

export const confirmRenewalCallback = (data: {
  provider: RenewalProvider;
  payment_id: string;
  data?: string; // eSewa's base64 callback payload
}): Promise<{ status: "completed" | "pending" }> =>
  httpClient({ method: "POST", url: "/api/v1/billing/renewals/callback", data });

// --- Member-facing invoices/receipts (FR-8.9, token-authenticated) --------

export const listMemberInvoices = (passToken: string): Promise<Invoice[]> =>
  httpClient({ method: "GET", url: `/api/v1/m/pass/${passToken}/invoices` });

export const fetchMemberInvoicePdf = (passToken: string, invoiceId: string): Promise<Blob> =>
  httpClient({
    method: "GET",
    url: `/api/v1/m/pass/${passToken}/invoices/${invoiceId}/pdf`,
    responseType: "blob",
  });

// --- Simple POS (FR-12.7) --------------------------------------------------

export interface Product {
  id: string;
  sku: string;
  name: string;
  price_npr: string;
  stock_qty: number;
  is_active: boolean;
}

export const listProducts = (): Promise<Product[] | Page<Product>> =>
  httpClient({ method: "GET", url: "/api/v1/products/" });

export const createProduct = (data: {
  sku: string;
  name: string;
  price_npr: string;
  stock_qty: number;
}): Promise<Product> => httpClient({ method: "POST", url: "/api/v1/products/", data });

export const updateProduct = (id: string, data: Partial<Product>): Promise<Product> =>
  httpClient({ method: "PATCH", url: `/api/v1/products/${id}/`, data });

export const deleteProduct = (id: string): Promise<void> =>
  httpClient({ method: "DELETE", url: `/api/v1/products/${id}/` });

export interface SaleLine {
  id: string;
  product: string;
  quantity: number;
  unit_price_npr: string;
  line_total_npr: string;
}

export interface Sale {
  id: string;
  invoice: string;
  created_by: string | null;
  created_at: string;
  lines: SaleLine[];
}

export const ringUpSale = (data: {
  member_id: string;
  lines: { product_id: string; quantity: number }[];
}): Promise<Sale> => httpClient({ method: "POST", url: "/api/v1/billing/sales", data });
