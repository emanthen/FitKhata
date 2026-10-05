import { describe, expect, it } from "vitest";
import { formatNpr } from "./money";

describe("formatNpr", () => {
  it.each([
    [0, "0.00"],
    [5, "5.00"],
    [50, "50.00"],
    [500, "500.00"],
    [5000, "5,000.00"],
    [50000, "50,000.00"],
    [100000, "1,00,000.00"],
    [1234567, "12,34,567.00"],
    [1234567.5, "12,34,567.50"],
    [12345678, "1,23,45,678.00"],
    [999, "999.00"],
    [1000, "1,000.00"],
  ])("formats %i as %s", (amount, expected) => {
    expect(formatNpr(amount)).toBe(expected);
  });

  it("handles negative amounts", () => {
    expect(formatNpr(-1234567.5)).toBe("-12,34,567.50");
  });

  it("rounds half-up", () => {
    expect(formatNpr(10.005)).toBe("10.01");
    expect(formatNpr(10.015)).toBe("10.02");
  });

  it("pads a single decimal digit", () => {
    expect(formatNpr(10.1)).toBe("10.10");
  });

  it("adds the Rs. symbol when requested", () => {
    expect(formatNpr(1234567.5, { symbol: true })).toBe("Rs. 12,34,567.50");
  });

  it("accepts string input", () => {
    expect(formatNpr("1234567.5")).toBe("12,34,567.50");
  });
});
