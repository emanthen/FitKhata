import { describe, expect, it } from "vitest";

import { classifyCheckin } from "./validate";
import type { CachedMember } from "./db";

// Mirrors the fixture shape and cases in
// apps/api/attendance/tests/test_services.py's classify_checkin tests.
const NOW = new Date(2026, 9, 4, 10, 0); // Oct 4 2026, 10:00 — "today"

function member(overrides: Partial<CachedMember> = {}): CachedMember {
  return {
    member_code: "ATT1-000001",
    member_id: 1,
    qr_secret_hex: "00".repeat(32),
    status: "active",
    expiry_date: "2026-10-31",
    access_hours: {},
    dues_npr: "0.00",
    photo_url: null,
    card_uid: "",
    updated_at: NOW.toISOString(),
    local_last_check_in_at: null,
    ...overrides,
  };
}

describe("classifyCheckin", () => {
  it("is green for a healthy active member", () => {
    expect(classifyCheckin(member(), NOW)).toBe("green");
  });

  it("is red for a frozen member", () => {
    expect(classifyCheckin(member({ status: "frozen" }), NOW)).toBe("red");
  });

  it("is red for an expired membership", () => {
    expect(classifyCheckin(member({ expiry_date: "2026-09-30" }), NOW)).toBe("red");
  });

  it("is amber within the near-expiry threshold", () => {
    expect(classifyCheckin(member({ expiry_date: "2026-10-06" }), NOW)).toBe("amber"); // 2 days left
  });

  it("is red for unpaid dues even with a healthy membership", () => {
    expect(classifyCheckin(member({ dues_npr: "3000.00" }), NOW)).toBe("red");
  });

  it("is red for an anti-passback violation within the window", () => {
    const twoMinutesAgo = new Date(NOW.getTime() - 2 * 60_000).toISOString();
    expect(classifyCheckin(member({ local_last_check_in_at: twoMinutesAgo }), NOW)).toBe("red");
  });

  it("allows a re-entry once the anti-passback window has passed", () => {
    const tenMinutesAgo = new Date(NOW.getTime() - 10 * 60_000).toISOString();
    expect(classifyCheckin(member({ local_last_check_in_at: tenMinutesAgo }), NOW)).toBe("green");
  });

  it("is red outside the member's access hours", () => {
    const hours = { windows: [{ day: "sun", start: "06:00", end: "22:00" }] };
    // Oct 4 2026 is a Sunday; 10:00 is inside that window, so push "now"
    // to a time outside it instead.
    const lateNight = new Date(2026, 9, 4, 23, 0);
    expect(classifyCheckin(member({ access_hours: hours }), lateNight)).toBe("red");
  });
});
