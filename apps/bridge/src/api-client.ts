import type { BatchCheckinResult, PendingCheckin, SnapshotMember } from "./types.js";

export interface BridgeApiConfig {
  baseUrl: string; // e.g. https://api.fitkhata.com/api/v1
  deviceToken: string;
}

function authHeaders(config: BridgeApiConfig): Record<string, string> {
  return {
    "content-type": "application/json",
    authorization: `Bearer ${config.deviceToken}`,
  };
}

/** Matches attendance/serializers.py's GateCheckinsBatchSerializer.MAX_BATCH_SIZE. */
export const MAX_BATCH_SIZE = 100;

export async function postCheckinsBatch(
  config: BridgeApiConfig,
  checkins: PendingCheckin[]
): Promise<BatchCheckinResult> {
  const res = await fetch(`${config.baseUrl}/gate/checkins:batch`, {
    method: "POST",
    headers: authHeaders(config),
    body: JSON.stringify({ checkins }),
  });
  if (!res.ok) {
    throw new Error(`gate/checkins:batch failed with status ${res.status}`);
  }
  return (await res.json()) as BatchCheckinResult;
}

export async function postHeartbeat(config: BridgeApiConfig): Promise<void> {
  const res = await fetch(`${config.baseUrl}/gate/heartbeat`, {
    method: "POST",
    headers: authHeaders(config),
  });
  if (!res.ok) {
    throw new Error(`gate/heartbeat failed with status ${res.status}`);
  }
}

export interface GateSnapshot {
  members: SnapshotMember[];
  staff: unknown[];
  server_time: string;
}

export async function getSnapshot(config: BridgeApiConfig, since?: string): Promise<GateSnapshot> {
  const url = new URL(`${config.baseUrl}/gate/snapshot`);
  if (since) url.searchParams.set("since", since);
  const res = await fetch(url, { headers: authHeaders(config) });
  if (!res.ok) {
    throw new Error(`gate/snapshot failed with status ${res.status}`);
  }
  return (await res.json()) as GateSnapshot;
}

export async function pairDevice(
  baseUrl: string,
  code: string,
  deviceName: string
): Promise<{ device_id: number; gym_id: string; token: string }> {
  const res = await fetch(`${baseUrl}/gate/pair`, {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({ code, device_name: deviceName }),
  });
  if (!res.ok) {
    throw new Error(`gate/pair failed with status ${res.status}`);
  }
  return (await res.json()) as { device_id: number; gym_id: string; token: string };
}
