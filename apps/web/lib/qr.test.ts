import { describe, expect, it } from "vitest";
import vectors from "../../../shared/qr_vectors.json";
import { bytesToHex, generateToken, hexToBytes, verify, windowFor } from "./qr";

interface Vector {
  secret_hex: string;
  unix_time: number;
  expected_token: string;
}

describe("qr vectors", () => {
  it("has 20 entries", () => {
    expect(vectors.length).toBe(20);
  });

  it.each(vectors as Vector[])(
    "generateToken matches vector for unix_time=$unix_time",
    async ({ secret_hex, unix_time, expected_token }) => {
      const secret = hexToBytes(secret_hex);
      const token = await generateToken(secret, windowFor(unix_time));
      expect(token).toBe(expected_token);
    }
  );
});

describe("bytesToHex", () => {
  it("round-trips through hexToBytes", () => {
    const hex = "0f1e2d3c4b5a6978";
    expect(bytesToHex(hexToBytes(hex))).toBe(hex);
  });
});

describe("windowFor", () => {
  it("buckets into 30-second windows", () => {
    expect(windowFor(0)).toBe(0);
    expect(windowFor(29)).toBe(0);
    expect(windowFor(30)).toBe(1);
    expect(windowFor(59)).toBe(1);
    expect(windowFor(60)).toBe(2);
  });
});

describe("verify", () => {
  it("accepts the current window", async () => {
    const secret = hexToBytes("11".repeat(32));
    const now = 1_700_000_000;
    const token = await generateToken(secret, windowFor(now));
    expect(await verify(secret, token, now)).toBe(true);
  });

  it("accepts adjacent windows", async () => {
    const secret = hexToBytes("22".repeat(32));
    const now = 1_700_000_000;
    const token = await generateToken(secret, windowFor(now));
    expect(await verify(secret, token, now - 30)).toBe(true);
    expect(await verify(secret, token, now + 30)).toBe(true);
  });

  it("rejects a token presented more than 60s later (acceptance: stale screenshot)", async () => {
    const secret = hexToBytes("33".repeat(32));
    const generatedAt = 1_700_000_000;
    const token = await generateToken(secret, windowFor(generatedAt));
    expect(await verify(secret, token, generatedAt + 90)).toBe(false);
  });

  it("rejects a token generated with a different secret", async () => {
    const now = 1_700_000_000;
    const token = await generateToken(hexToBytes("55".repeat(32)), windowFor(now));
    expect(await verify(hexToBytes("66".repeat(32)), token, now)).toBe(false);
  });
});
