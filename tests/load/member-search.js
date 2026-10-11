// H2 scenario 2: member search (FR-2.12's trigram-indexed GET /members?q=).
// Target: p95 < 300ms (read).
//
// Needs a staff JWT + gym id for a gym that actually has a realistic
// member count seeded (the FR-2.12 benchmark is explicitly against 10,000
// members -- `make seed` already seeds this per Phase 2's acceptance
// check, so point this at a seeded gym, not an empty one).
//
// Run: k6 run -e BASE_URL=... -e STAFF_JWT=... -e GYM_ID=... tests/load/member-search.js

import http from "k6/http";
import { check } from "k6";
import { BASE_URL, authHeaders } from "./lib/config.js";

const QUERIES = [
  "ram", "sita", "98", "FK-0", "shrestha", "gurung", "9841", "maya", "bahadur", "rai",
];

export const options = {
  scenarios: {
    search: {
      executor: "constant-vus",
      vus: 30,
      duration: "2m",
    },
  },
  thresholds: {
    http_req_duration: ["p(95)<300"],
    checks: ["rate>0.99"],
  },
};

export default function () {
  const q = QUERIES[Math.floor(Math.random() * QUERIES.length)];
  const res = http.get(`${BASE_URL}/api/v1/members/?q=${encodeURIComponent(q)}`, {
    headers: authHeaders(),
  });
  check(res, { "status is 200": (r) => r.status === 200 });
}
