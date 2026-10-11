import type { BridgeApiConfig } from "../api-client.js";
import { postHeartbeat } from "../api-client.js";

/** 60s-interval liveness ping -> GateDevice.last_seen_at (see
 * attendance/views.py::GateHeartbeatView). Failures are swallowed -- a
 * missed heartbeat during a network blip just means the owner alert
 * (attendance/tasks.py::alert_offline_gate_devices) fires a bit later, not
 * that the bridge process should crash. */
export function startHeartbeatLoop(config: BridgeApiConfig, intervalMs = 60_000): () => void {
  const timer = setInterval(() => {
    postHeartbeat(config).catch(() => undefined);
  }, intervalMs);
  return () => clearInterval(timer);
}
