// H2 scenario 3: owner dashboard (FR-10.1's combined summary endpoint --
// one round trip for active members, revenue today/month, renewals due,
// red list count). Target: p95 < 300ms (read) -- this one's explicitly
// supposed to load in under 2s end-to-end per Phase 10's own acceptance
// check, so 300ms at the API layer leaves real headroom for the frontend.
//
// Run: k6 run -e BASE_URL=... -e STAFF_JWT=... -e GYM_ID=... tests/load/owner-dashboard.js

import http from "k6/http";
import { check } from "k6";
import { BASE_URL, authHeaders } from "./lib/config.js";

export const options = {
  scenarios: {
    dashboard: {
      executor: "constant-vus",
      vus: 20,
      duration: "2m",
    },
  },
  thresholds: {
    http_req_duration: ["p(95)<300"],
    checks: ["rate>0.99"],
  },
};

export default function () {
  const res = http.get(`${BASE_URL}/api/v1/reports/dashboard-summary`, {
    headers: authHeaders(),
  });
  check(res, { "status is 200": (r) => r.status === 200 });
}
