// H2 scenario 4: payment initiate -- desk cash collection
// (POST /api/v1/billing/payments), which exercises the real write path
// end to end: select_for_update on the Payment row, the idempotency
// check, invoice issuance logic, AuditLog write, and the notify()/
// webhook dispatch added for FR-12.4. Target: p95 < 600ms (write).
//
// Deliberately pays a tiny partial amount (NPR 1.00) against each
// invoice rather than paying it off in full -- a fully-paid invoice makes
// every later request against the same invoice_id hit collect_payment's
// "already completed" idempotent short-circuit instead of the real
// write path, which would understate latency. Needs a pool of pre-seeded
// DRAFT invoices (each with a total well above NPR 1.00) provided as a
// JSON array of invoice ids via INVOICE_IDS_FILE -- there's no way to
// run this meaningfully without real seeded invoices.
//
// Run: k6 run -e BASE_URL=... -e STAFF_JWT=... -e GYM_ID=... -e INVOICE_IDS_FILE=./data/draft-invoice-ids.json tests/load/payment-initiate.js

import http from "k6/http";
import { check } from "k6";
import { SharedArray } from "k6/data";
import { BASE_URL, authHeaders } from "./lib/config.js";

const invoiceIds = new SharedArray("draft invoice ids", function () {
  const path = __ENV.INVOICE_IDS_FILE || "./data/draft-invoice-ids.json";
  try {
    return JSON.parse(open(path));
  } catch {
    return ["REPLACE_WITH_A_REAL_DRAFT_INVOICE_ID"]; // local smoke-test only
  }
});

export const options = {
  scenarios: {
    collect_payment: {
      executor: "constant-vus",
      vus: 15,
      duration: "2m",
    },
  },
  thresholds: {
    http_req_duration: ["p(95)<600"],
    checks: ["rate>0.99"],
  },
};

export default function () {
  const invoiceId = invoiceIds[Math.floor(Math.random() * invoiceIds.length)];
  const res = http.post(
    `${BASE_URL}/api/v1/billing/payments`,
    JSON.stringify({ invoice_id: invoiceId, mode: "cash", amount_npr: "1.00" }),
    { headers: authHeaders() }
  );
  check(res, { "status is 2xx": (r) => r.status >= 200 && r.status < 300 });
}
