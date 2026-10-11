import { describe, expect, it } from "vitest";

import type { SnapshotMember } from "../types.js";
import { isCheckinAllowed } from "./access.js";

const NOW = new Date("2026-10-11T06:00:00Z");

function member(overrides: Partial<SnapshotMember> = {}): SnapshotMember {
  return {
    member_code: "GYM1-0001",
    member_id: 1,
    status: "active",
    expiry_date: "2026-12-01",
    updated_at: NOW.toISOString(),
    ...overrides,
  };
}

describe("isCheckinAllowed", () => {
  it("allows an active member with a future expiry", () => {
    expect(isCheckinAllowed(member(), NOW)).toBe(true);
  });

  it("allows a trial member", () => {
    expect(isCheckinAllowed(member({ status: "trial" }), NOW)).toBe(true);
  });

  it("allows an active member with no membership on file yet", () => {
    expect(isCheckinAllowed(member({ expiry_date: null }), NOW)).toBe(true);
  });

  it("denies an expired member", () => {
    expect(isCheckinAllowed(member({ status: "expired" }), NOW)).toBe(false);
  });

  it("denies a frozen member", () => {
    expect(isCheckinAllowed(member({ status: "frozen" }), NOW)).toBe(false);
  });

  it("denies a cancelled member", () => {
    expect(isCheckinAllowed(member({ status: "cancelled" }), NOW)).toBe(false);
  });

  it("denies an active-status member whose membership already expired", () => {
    expect(isCheckinAllowed(member({ expiry_date: "2026-10-01" }), NOW)).toBe(false);
  });

  it("allows right up to and including the expiry date itself", () => {
    expect(isCheckinAllowed(member({ expiry_date: "2026-10-11" }), NOW)).toBe(true);
  });
});
