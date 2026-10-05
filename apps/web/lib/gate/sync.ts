import { fetchGateSnapshot, postCheckinsBatch } from "@fitkhata/api-client";

import { getDeviceAuth } from "./auth";
import { decryptTransportSecret, deriveTransportKey } from "./crypto";
import {
  getLastSyncAt,
  pendingCheckins,
  removeSyncedCheckins,
  setLastSyncAt,
  upsertMemberFromSnapshot,
} from "./db";

export type SyncResult = "online" | "offline" | "sync-error";

const BATCH_SIZE = 100;
const INITIAL_BACKOFF_MS = 2_000;
const MAX_BACKOFF_MS = 60_000;

let backoffMs = INITIAL_BACKOFF_MS;

export function getBackoffMs(): number {
  return backoffMs;
}

/** Pulls members changed since the last snapshot, decrypts the server's
 * per-device transport encryption once, and caches the plaintext secret
 * locally (re-encrypted at rest — see db.ts's upsertMemberFromSnapshot).
 */
export async function refreshSnapshot(): Promise<void> {
  const auth = getDeviceAuth();
  if (!auth) return;

  const since = await getLastSyncAt();
  const response = await fetchGateSnapshot(auth.token, since ?? undefined);
  const transportKey = await deriveTransportKey(auth.token);

  for (const row of response.members) {
    const qrSecretHex = await decryptTransportSecret(transportKey, row.qr_secret);
    await upsertMemberFromSnapshot({
      member_code: row.member_code,
      member_id: row.member_id,
      qr_secret_hex: qrSecretHex,
      status: row.status,
      expiry_date: row.expiry_date,
      access_hours: row.access_hours,
      dues_npr: row.dues_npr,
      photo_url: row.photo_url,
      card_uid: row.card_uid,
      updated_at: row.updated_at,
    });
  }
  await setLastSyncAt(response.server_time);
}

/** Drains the outbox in batches of <=100 (POST /gate/checkins:batch's own
 * cap). Both "accepted" and "duplicates" are removed locally — a
 * duplicate just means a prior sync attempt already landed it server-side
 * (e.g. the response to an earlier attempt was lost but the write
 * succeeded); either way this device has nothing left to retry for it.
 */
export async function syncOutbox(): Promise<SyncResult> {
  const auth = getDeviceAuth();
  if (!auth) return "offline";
  if (typeof navigator !== "undefined" && !navigator.onLine) return "offline";

  const pending = await pendingCheckins();
  if (pending.length === 0) {
    backoffMs = INITIAL_BACKOFF_MS;
    return "online";
  }

  try {
    for (let i = 0; i < pending.length; i += BATCH_SIZE) {
      const chunk = pending.slice(i, i + BATCH_SIZE);
      const result = await postCheckinsBatch(
        auth.token,
        chunk.map((row) => ({
          client_uuid: row.client_uuid,
          member_code: row.member_code,
          check_in_at: row.check_in_at,
          source: row.source,
        }))
      );
      await removeSyncedCheckins([...result.accepted, ...result.duplicates]);
    }
    backoffMs = INITIAL_BACKOFF_MS;
    return "online";
  } catch {
    backoffMs = Math.min(backoffMs * 2, MAX_BACKOFF_MS);
    return "sync-error";
  }
}
