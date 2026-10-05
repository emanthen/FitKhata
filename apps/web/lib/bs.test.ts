import { describe, expect, it } from "vitest";
import { formatBs, toAd, toBs } from "./bs";

describe("toBs", () => {
  it.each([
    [Date.UTC(2013, 3, 14), [2070, 1, 1]],
    [Date.UTC(2023, 3, 14), [2080, 1, 1]],
    [Date.UTC(2025, 3, 14), [2082, 1, 1]],
    [Date.UTC(2026, 3, 14), [2083, 1, 1]],
    [Date.UTC(2026, 6, 17), [2083, 4, 1]],
    [Date.UTC(2026, 6, 16), [2083, 3, 32]],
    [Date.UTC(2026, 7, 15), [2083, 4, 30]],
    [Date.UTC(2026, 9, 1), [2083, 6, 15]],
  ])("converts %s to BS %o", (ms, [year, month, day]) => {
    expect(toBs(new Date(ms))).toEqual({ year, month, day });
  });

  it("rejects dates before the table", () => {
    expect(() => toBs(new Date(Date.UTC(2013, 3, 13)))).toThrow(RangeError);
  });
});

describe("toAd", () => {
  it("round-trips with toBs", () => {
    const ad = new Date(Date.UTC(2026, 6, 17));
    const bs = toBs(ad);
    expect(toAd(bs.year, bs.month, bs.day).getTime()).toBe(ad.getTime());
  });

  it("rejects an invalid day", () => {
    expect(() => toAd(2083, 1, 32)).toThrow(RangeError);
  });
});

describe("formatBs", () => {
  it("formats in English", () => {
    expect(formatBs(new Date(Date.UTC(2026, 6, 17)))).toBe("2083 Shrawan 1");
  });

  it("formats in Nepali", () => {
    expect(formatBs(new Date(Date.UTC(2026, 6, 17)), "ne")).toBe("२०८३ श्रावण १");
  });
});
