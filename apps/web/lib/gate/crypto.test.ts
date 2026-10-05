import { describe, expect, it } from "vitest";

import {
  decryptJson,
  decryptTransportSecret,
  deriveGateDbKey,
  deriveTransportKey,
  encryptJson,
} from "./crypto";
import { bytesToHex } from "../qr";

describe("local at-rest encryption (deriveGateDbKey)", () => {
  it("round-trips an arbitrary object through the same device token", async () => {
    const key = await deriveGateDbKey("test-device-token-abc123");
    const original = { member_code: "KTM1-0001", status: "active", dues_npr: "0.00" };

    const blob = await encryptJson(key, original);
    const decrypted = await decryptJson<typeof original>(key, blob);

    expect(decrypted).toEqual(original);
  });

  it("produces a different key for a different device token", async () => {
    const keyA = await deriveGateDbKey("device-a");
    const keyB = await deriveGateDbKey("device-b");
    const blob = await encryptJson(keyA, { secret: true });

    await expect(decryptJson(keyB, blob)).rejects.toBeDefined();
  });
});

/** Derives the same key as crypto.ts's deriveTransportKey, but with
 * "encrypt" usage — standing in for the server side of
 * attendance/crypto.py's encrypt_for_device (same HKDF info string), which
 * this test suite has no Python interpreter to actually run.
 */
async function deriveTransportKeyForEncrypting(rawToken: string): Promise<CryptoKey> {
  const baseKey = await crypto.subtle.importKey(
    "raw",
    new TextEncoder().encode(rawToken),
    "HKDF",
    false,
    ["deriveKey"]
  );
  return crypto.subtle.deriveKey(
    {
      name: "HKDF",
      hash: "SHA-256",
      salt: new Uint8Array(0),
      info: new TextEncoder().encode("fitkhata-gate-device-key"),
    },
    baseKey,
    { name: "AES-GCM", length: 256 },
    false,
    ["encrypt"]
  );
}

describe("transport decryption (deriveTransportKey)", () => {
  it("decrypts a payload encrypted under the same HKDF-derived key", async () => {
    const rawToken = "test-device-token-abc123";
    const encryptKey = await deriveTransportKeyForEncrypting(rawToken);

    const plaintext = new TextEncoder().encode("0123456789abcdef0123456789abcdef");
    const nonce = crypto.getRandomValues(new Uint8Array(12));
    const ciphertext = await crypto.subtle.encrypt(
      { name: "AES-GCM", iv: nonce },
      encryptKey,
      plaintext
    );

    const decryptKey = await deriveTransportKey(rawToken);
    const result = await decryptTransportSecret(decryptKey, {
      nonce: bytesToHex(nonce),
      ciphertext: bytesToHex(new Uint8Array(ciphertext)),
    });

    expect(result).toBe(bytesToHex(plaintext));
  });
});
