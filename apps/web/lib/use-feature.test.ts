import { describe, expect, it } from "vitest";

import { resolveFeature } from "./use-feature";

describe("resolveFeature", () => {
  it("fails open when the key is missing from features", () => {
    expect(resolveFeature({}, "red_list")).toBe(true);
  });

  it("fails open when features is undefined (query still loading)", () => {
    expect(resolveFeature(undefined, "red_list")).toBe(true);
  });

  it("respects an explicit true", () => {
    expect(resolveFeature({ red_list: true }, "red_list")).toBe(true);
  });

  it("respects an explicit false", () => {
    expect(resolveFeature({ red_list: false }, "red_list")).toBe(false);
  });
});
