import { randomUUID } from "node:crypto";
import { spawn } from "node:child_process";

import type { PendingCheckin, SnapshotMember } from "../types.js";
import { ZkSidecarClient } from "./zk-sidecar-client.js";

/** Spawns the pyzk sidecar (sidecar/zk_sidecar.py in dev, a PyInstaller
 * binary in production packaging -- see the plan's reasoning for pyzk over
 * a pure-Node ZKTeco library). `binaryPath` defaults to the dev invocation;
 * production config points it at the packaged standalone executable. */
export function spawnZkSidecar(
  binaryPath = "python",
  scriptPath = new URL("../../sidecar/zk_sidecar.py", import.meta.url).pathname
): ZkSidecarClient {
  const isPythonInterpreter = /python3?(\.exe)?$/i.test(binaryPath);
  const child = spawn(isPythonInterpreter ? binaryPath : binaryPath, isPythonInterpreter ? [scriptPath] : [], {
    stdio: ["pipe", "pipe", "inherit"],
  });
  return new ZkSidecarClient({ stdin: child.stdin, stdout: child.stdout });
}

export type MemberCodeResolver = (deviceUserId: string) => string | undefined;

/** One polling tick: pulls whatever attendance rows the device has logged
 * since `sinceOffset`, maps each device user_id -> member_code via the
 * resolver (fed by the /gate/snapshot the bridge already syncs), and hands
 * off a PendingCheckin per resolved row. An unresolvable user_id is skipped,
 * not fatal -- it just means the device has a user FitKhata doesn't know
 * about yet (stale enrolment), which enrolment push/delete should prevent
 * in steady state.
 *
 * Returns the offset to persist and pass as `sinceOffset` next tick. */
export async function pollAttendanceOnce(
  client: ZkSidecarClient,
  sinceOffset: number,
  resolveMemberCode: MemberCodeResolver,
  onCheckin: (row: PendingCheckin) => void
): Promise<number> {
  const { rows, nextOffset } = await client.pollAttendance(sinceOffset);

  for (const row of rows) {
    const memberCode = resolveMemberCode(row.user_id);
    if (!memberCode) continue;
    onCheckin({
      client_uuid: randomUUID(),
      member_code: memberCode,
      check_in_at: row.timestamp,
      source: "biometric",
      created_at: new Date().toISOString(),
    });
  }

  return nextOffset;
}

export async function enrollMember(
  client: ZkSidecarClient,
  deviceUserId: string,
  memberCode: string
): Promise<void> {
  await client.setUser(deviceUserId, memberCode);
}

export async function removeMember(client: ZkSidecarClient, deviceUserId: string): Promise<void> {
  await client.deleteUser(deviceUserId);
}

export async function setMemberEnabled(
  client: ZkSidecarClient,
  deviceUserId: string,
  enabled: boolean
): Promise<void> {
  await client.setEnabled(deviceUserId, enabled);
}

/** Pushes one member's device-side enrolment to match their current
 * FitKhata status, per the spec: enrol active/trial members (device
 * user_id = their numeric member_id, per index.ts's convention),
 * delete on cancellation (no card/finger match left to deny entry
 * against), disable on expiry/freeze (see setMemberEnabled's own
 * ceiling note on what "disable" actually does on a pyzk device).
 * Called once per changed member in a /gate/snapshot delta -- safe to
 * call repeatedly for an already-correct state (set_user is an upsert,
 * delete/disable on an absent user is a no-op per the sidecar). */
export async function syncEnrollment(
  client: ZkSidecarClient,
  member: SnapshotMember
): Promise<void> {
  const deviceUserId = String(member.member_id);
  if (member.status === "cancelled") {
    await removeMember(client, deviceUserId);
  } else if (member.status === "expired" || member.status === "frozen") {
    await setMemberEnabled(client, deviceUserId, false);
  } else {
    await enrollMember(client, deviceUserId, member.member_code);
  }
}
