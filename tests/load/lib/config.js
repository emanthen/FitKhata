// Shared config for every scenario script. Nothing here talks to the API
// directly -- it just centralizes how each script reads its target and
// credentials, so there's one place to change when pointing at a
// different staging target.
//
// Every value is read from a k6 `-e NAME=value` flag or env var, with a
// safe-for-local default where one makes sense. Nothing is hardcoded that
// would accidentally hit a real production host.

export const BASE_URL = __ENV.BASE_URL || "http://localhost:8000";

// A staff JWT access token for the gym under test -- mint one with
// `accounts.tokens.issue_tokens_for_user` against a seeded staff user, or
// via the normal /api/v1/auth/login flow against staging. Required for
// member-search.js, owner-dashboard.js, and payment-initiate.js.
export const STAFF_JWT = __ENV.STAFF_JWT || "";
export const GYM_ID = __ENV.GYM_ID || "";

export function authHeaders() {
  return {
    "content-type": "application/json",
    authorization: `Bearer ${STAFF_JWT}`,
    "x-gym-id": GYM_ID,
  };
}
