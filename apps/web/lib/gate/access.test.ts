import { describe, expect, it } from "vitest";

import { isWithinAccessHours } from "./access";

// Oct 5 2026 is a Monday, Oct 6 2026 is a Tuesday — same fixture dates as
// apps/api/members/domain/tests/test_access.py, so the two suites are
// trivially comparable.

describe("isWithinAccessHours", () => {
  it("is unrestricted for an empty object", () => {
    expect(isWithinAccessHours({}, new Date(2026, 9, 5, 3, 0))).toBe(true);
  });

  it("is unrestricted for explicit always:true", () => {
    expect(isWithinAccessHours({ always: true }, new Date(2026, 9, 5, 3, 0))).toBe(true);
  });

  it("allows a time inside a window", () => {
    const hours = { windows: [{ day: "mon", start: "06:00", end: "22:00" }] };
    expect(isWithinAccessHours(hours, new Date(2026, 9, 5, 12, 0))).toBe(true);
  });

  it("rejects a time outside a window on the same day", () => {
    const hours = { windows: [{ day: "mon", start: "06:00", end: "22:00" }] };
    expect(isWithinAccessHours(hours, new Date(2026, 9, 5, 23, 0))).toBe(false);
  });

  it("rejects the wrong day", () => {
    const hours = { windows: [{ day: "mon", start: "06:00", end: "22:00" }] };
    expect(isWithinAccessHours(hours, new Date(2026, 9, 6, 12, 0))).toBe(false);
  });

  it("includes both window boundaries", () => {
    const hours = { windows: [{ day: "mon", start: "06:00", end: "22:00" }] };
    expect(isWithinAccessHours(hours, new Date(2026, 9, 5, 6, 0))).toBe(true);
    expect(isWithinAccessHours(hours, new Date(2026, 9, 5, 22, 0))).toBe(true);
  });

  it("unions multiple windows on the same day", () => {
    const hours = {
      windows: [
        { day: "mon", start: "05:00", end: "09:00" },
        { day: "mon", start: "17:00", end: "21:00" },
      ],
    };
    expect(isWithinAccessHours(hours, new Date(2026, 9, 5, 7, 0))).toBe(true);
    expect(isWithinAccessHours(hours, new Date(2026, 9, 5, 12, 0))).toBe(false);
    expect(isWithinAccessHours(hours, new Date(2026, 9, 5, 18, 0))).toBe(true);
  });
});
