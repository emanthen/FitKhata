/**
 * Gate QR token algorithm. Mirrors apps/api/core/domain/qr.py byte-for-byte
 * — both are tested against the same shared/qr_vectors.json.
 *
 * window = floor(unix_seconds / 30)
 * mac = HMAC-SHA256(secret, window as 8-byte big-endian)
 * token = base32(mac)[0:10]
 * payload = `${gymCode}.${memberCode}.${token}`
 *
 * Uses the WebCrypto SubtleCrypto API (not Node's `crypto` module) so this
 * runs unmodified in the browser (gate/member PWAs) and in Node/vitest —
 * SubtleCrypto is global in both. That makes every function here async,
 * unlike the synchronous Python version.
 */

const WINDOW_SECONDS = 30;
const TOKEN_LENGTH = 10;

const BASE32_ALPHABET = "ABCDEFGHIJKLMNOPQRSTUVWXYZ234567";

function base32Encode(bytes: Uint8Array): string {
  let bits = 0;
  let value = 0;
  let output = "";
  for (const byte of bytes) {
    value = (value << 8) | byte;
    bits += 8;
    while (bits >= 5) {
      output += BASE32_ALPHABET[(value >>> (bits - 5)) & 0x1f];
      bits -= 5;
    }
  }
  if (bits > 0) {
    output += BASE32_ALPHABET[(value << (5 - bits)) & 0x1f];
  }
  return output;
}

export function windowFor(unixSeconds: number): number {
  return Math.floor(unixSeconds / WINDOW_SECONDS);
}

function windowToBytes(window: number): Uint8Array {
  // 8-byte big-endian, matching Python's int.to_bytes(8, "big"). window
  // fits comfortably in a JS safe integer for any realistic unix time.
  const buf = new ArrayBuffer(8);
  const view = new DataView(buf);
  view.setUint32(0, Math.floor(window / 2 ** 32), false);
  view.setUint32(4, window >>> 0, false);
  return new Uint8Array(buf);
}

async function hmacSha256(secret: Uint8Array, message: Uint8Array): Promise<Uint8Array> {
  // `as BufferSource`: @types/node's Uint8Array<ArrayBufferLike> and lib.dom's
  // BufferSource (which wants ArrayBuffer specifically, not ArrayBufferLike)
  // disagree here even though this is always a plain in-memory ArrayBuffer.
  const key = await crypto.subtle.importKey(
    "raw",
    secret as BufferSource,
    { name: "HMAC", hash: "SHA-256" },
    false,
    ["sign"]
  );
  const signature = await crypto.subtle.sign("HMAC", key, message as BufferSource);
  return new Uint8Array(signature);
}

export async function generateToken(secret: Uint8Array, window: number): Promise<string> {
  const mac = await hmacSha256(secret, windowToBytes(window));
  return base32Encode(mac).slice(0, TOKEN_LENGTH);
}

export async function payloadFor(
  gymCode: string,
  memberCode: string,
  secret: Uint8Array,
  unixSeconds: number
): Promise<string> {
  const token = await generateToken(secret, windowFor(unixSeconds));
  return `${gymCode}.${memberCode}.${token}`;
}

/**
 * True if token matches this secret for window w-1, w, or w+1. gymCode/
 * memberCode aren't part of the MAC (only window is) — they're a lookup
 * key in the payload, not a binding; see qr.py's verify() docstring.
 */
export async function verify(
  secret: Uint8Array,
  token: string,
  unixSeconds: number
): Promise<boolean> {
  const window = windowFor(unixSeconds);
  for (const w of [window - 1, window, window + 1]) {
    const candidate = await generateToken(secret, w);
    if (timingSafeEqual(candidate, token)) return true;
  }
  return false;
}

function timingSafeEqual(a: string, b: string): boolean {
  // Constant-time-ish comparison (always walks the longer string's full
  // length) — mirrors Python's hmac.compare_digest as defense-in-depth,
  // not a hard requirement for a 30s-lived token.
  const len = Math.max(a.length, b.length);
  let diff = a.length ^ b.length;
  for (let i = 0; i < len; i++) {
    diff |= (a.charCodeAt(i) || 0) ^ (b.charCodeAt(i) || 0);
  }
  return diff === 0;
}

export function hexToBytes(hex: string): Uint8Array {
  const bytes = new Uint8Array(hex.length / 2);
  for (let i = 0; i < bytes.length; i++) {
    bytes[i] = parseInt(hex.slice(i * 2, i * 2 + 2), 16);
  }
  return bytes;
}

export function bytesToHex(bytes: Uint8Array): string {
  return Array.from(bytes, (b) => b.toString(16).padStart(2, "0")).join("");
}
