import { httpClient } from "./http-client";
import type { Page } from "./members";

export interface InvoiceLine {
  id: string;
  description: string;
  quantity: number;
  unit_price_npr: string;
  line_total_npr: string;
}

export interface Invoice {
  id: string;
  number: string;
  fiscal_year: number;
  status: "draft" | "void";
  member: string;
  subtotal_npr: string;
  discount_npr: string;
  total_npr: string;
  lines: InvoiceLine[];
  created_at: string;
}

export const listInvoices = (memberId: string): Promise<Invoice[] | Page<Invoice>> =>
  httpClient({ method: "GET", url: "/api/v1/invoices/", params: { member: memberId } });
