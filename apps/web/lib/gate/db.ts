import Dexie, { type Table } from "dexie";

import { decryptJson, deriveGateDbKey, encryptJson, type EncryptedBlob } from "./crypto";
import { getDeviceAuth } from "./auth";
import type { AccessHours } from "./access";
import type { CheckinSource } from "@fitkhata/api-client";

/** The kiosk's cached view of a member — a decrypted mirror of the fields
 * GateSnapshotView returns, plus one purely-local field
 * (local_last_check_in_at) this device maintains itself for anti-passback.
 * `qr_secret_hex` here is already decrypted (the AES-GCM transport layer
 * from the server is undone once, right after fetching the snapshot — see
 * lib/gate/sync.ts) before being re-encrypted at rest under this device's
 * own local key.
 */
export interface CachedMember {
  member_code: string;
  member_id: number;
  qr_secret_hex: string;
  status: string;
  expiry_date: string | null;
  access_hours: AccessHours;
  dues_npr: string;
  photo_url: string | null;
  card_uid: string;
  updated_at: string;
  local_last_check_in_at: string | null;
}

export interface OutboxRow {
  client_uuid: string;
  member_code: string;
  check_in_at: string;
  source: CheckinSource;
}

interface MemberRow {
  member_code: string;
  blob: EncryptedBlob;
}

interface MetaRow {
  id: string;
  last_sync_at: string | null;
}

const META_SINGLETON_ID = "singleton";

class GateDb extends Dexie {
  members!: Table<MemberRow, string>;
  outbox!: Table<OutboxRow, string>;
  meta!: Table<MetaRow, string>;

  constructor() {
    super("fitkhata-gate");
    this.version(1).stores({
      members: "member_code",
      outbox: "client_uuid, member_code",
      meta: "id",
    });
  }
}

export const gateDb = new GateDb();

let cachedKey: CryptoKey | null = null;

async function dbKey(): Promise<CryptoKey> {
  if (cachedKey) return cachedKey;
  const auth = getDeviceAuth();
  if (!auth) throw new Error("Device is not paired.");
  cachedKey = await deriveGateDbKey(auth.token);
  return cachedKey;
}

/** Call once after pairing/unpairing so a stale key from a previous
 * pairing is never reused.
 */
export function resetDbKeyCache(): void {
  cachedKey = null;
}

export async function getMemberByCode(memberCode: string): Promise<CachedMember | null> {
  const row = await gateDb.members.get(memberCode);
  if (!row) return null;
  const key = await dbKey();
  return decryptJson<CachedMember>(key, row.blob);
}

/** Linear decrypt-scan rather than a plaintext card_uid index: rosters are
 * thousands, not millions, of members per gym, and indexing card_uid in
 * the clear would defeat the point of encrypting this table at rest.
 */
export async function getMemberByCardUid(cardUid: string): Promise<CachedMember | null> {
  const key = await dbKey();
  const rows = await gateDb.members.toArray();
  for (const row of rows) {
    const member = await decryptJson<CachedMember>(key, row.blob);
    if (member.card_uid && member.card_uid === cardUid) return member;
  }
  return null;
}

/** Upserts a member, preserving the local-only local_last_check_in_at
 * field across snapshot refreshes (the server doesn't know about it).
 */
export async function upsertMemberFromSnapshot(
  fields: Omit<CachedMember, "local_last_check_in_at">
): Promise<void> {
  const existing = await getMemberByCode(fields.member_code);
  const merged: CachedMember = {
    ...fields,
    local_last_check_in_at: existing?.local_last_check_in_at ?? null,
  };
  const key = await dbKey();
  const blob = await encryptJson(key, merged);
  await gateDb.members.put({ member_code: merged.member_code, blob });
}

export async function markLocalCheckin(memberCode: string, checkInAtIso: string): Promise<void> {
  const existing = await getMemberByCode(memberCode);
  if (!existing) return;
  const key = await dbKey();
  const blob = await encryptJson(key, { ...existing, local_last_check_in_at: checkInAtIso });
  await gateDb.members.put({ member_code: memberCode, blob });
}

export async function enqueueCheckin(row: OutboxRow): Promise<void> {
  await gateDb.outbox.put(row);
}

export async function pendingCheckins(): Promise<OutboxRow[]> {
  return gateDb.outbox.toArray();
}

export async function pendingCount(): Promise<number> {
  return gateDb.outbox.count();
}

export async function removeSyncedCheckins(clientUuids: string[]): Promise<void> {
  await gateDb.outbox.bulkDelete(clientUuids);
}

export async function getLastSyncAt(): Promise<string | null> {
  const row = await gateDb.meta.get(META_SINGLETON_ID);
  return row?.last_sync_at ?? null;
}

export async function setLastSyncAt(iso: string): Promise<void> {
  await gateDb.meta.put({ id: META_SINGLETON_ID, last_sync_at: iso });
}
