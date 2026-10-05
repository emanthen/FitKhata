/** Encrypts the kiosk's local Dexie cache at rest. Key is derived
 * (WebCrypto HKDF-SHA256) from the device's own raw token, the same shape
 * as apps/api/attendance/crypto.py's derive_device_key — but a different
 * `info` string and purpose: that one derives a per-request transport key
 * for the server to encrypt the snapshot payload with; this one derives a
 * local-only key so the roster sitting in IndexedDB isn't plaintext if the
 * tablet is lost or examined offline. Never sent anywhere.
 */
import { bytesToHex, hexToBytes } from "../qr";

const HKDF_INFO = new TextEncoder().encode("fitkhata-gate-local-db");

export interface EncryptedBlob {
  iv: string;
  data: string;
}

export async function deriveGateDbKey(rawToken: string): Promise<CryptoKey> {
  const baseKey = await crypto.subtle.importKey(
    "raw",
    new TextEncoder().encode(rawToken),
    "HKDF",
    false,
    ["deriveKey"]
  );
  return crypto.subtle.deriveKey(
    { name: "HKDF", hash: "SHA-256", salt: new Uint8Array(0), info: HKDF_INFO },
    baseKey,
    { name: "AES-GCM", length: 256 },
    false,
    ["encrypt", "decrypt"]
  );
}

export async function encryptJson(key: CryptoKey, value: unknown): Promise<EncryptedBlob> {
  const iv = crypto.getRandomValues(new Uint8Array(12));
  const plaintext = new TextEncoder().encode(JSON.stringify(value));
  const ciphertext = await crypto.subtle.encrypt({ name: "AES-GCM", iv }, key, plaintext);
  return { iv: bytesToHex(iv), data: bytesToHex(new Uint8Array(ciphertext)) };
}

export async function decryptJson<T>(key: CryptoKey, blob: EncryptedBlob): Promise<T> {
  const iv = hexToBytes(blob.iv);
  const ciphertext = hexToBytes(blob.data);
  const plaintext = await crypto.subtle.decrypt(
    { name: "AES-GCM", iv: iv as BufferSource },
    key,
    ciphertext as BufferSource
  );
  return JSON.parse(new TextDecoder().decode(plaintext)) as T;
}

/** Undoes the server's per-request transport encryption (GateSnapshotView
 * + attendance/crypto.py's encrypt_for_device) — a *different* derivation
 * than deriveGateDbKey above: same HKDF shape, but the server's own
 * `info` string (must match attendance/crypto.py's _HKDF_INFO exactly),
 * and for decrypt only. The resulting plaintext is then re-encrypted at
 * rest under deriveGateDbKey before being cached — see lib/gate/sync.ts.
 */
const TRANSPORT_HKDF_INFO = new TextEncoder().encode("fitkhata-gate-device-key");

export async function deriveTransportKey(rawToken: string): Promise<CryptoKey> {
  const baseKey = await crypto.subtle.importKey(
    "raw",
    new TextEncoder().encode(rawToken),
    "HKDF",
    false,
    ["deriveKey"]
  );
  return crypto.subtle.deriveKey(
    { name: "HKDF", hash: "SHA-256", salt: new Uint8Array(0), info: TRANSPORT_HKDF_INFO },
    baseKey,
    { name: "AES-GCM", length: 256 },
    false,
    ["decrypt"]
  );
}

export async function decryptTransportSecret(
  key: CryptoKey,
  payload: { nonce: string; ciphertext: string }
): Promise<string> {
  const iv = hexToBytes(payload.nonce);
  const ciphertext = hexToBytes(payload.ciphertext);
  const plaintext = await crypto.subtle.decrypt(
    { name: "AES-GCM", iv: iv as BufferSource },
    key,
    ciphertext as BufferSource
  );
  return bytesToHex(new Uint8Array(plaintext));
}
