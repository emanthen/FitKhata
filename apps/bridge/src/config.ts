import { homedir } from "node:os";
import { join } from "node:path";

function env(name: string, fallback?: string): string {
  const value = process.env[name] ?? fallback;
  if (value === undefined) throw new Error(`missing required env var: ${name}`);
  return value;
}

export const config = {
  apiBaseUrl: env("FITKHATA_API_BASE_URL", "https://api.fitkhata.com/api/v1"),
  webOrigin: env("FITKHATA_WEB_ORIGIN", "https://app.fitkhata.com"),
  healthzPort: Number(process.env.PORT ?? 7070),
  printPort: Number(process.env.FITKHATA_PRINT_PORT ?? 7777),
  dataDir: process.env.FITKHATA_BRIDGE_DATA_DIR ?? join(homedir(), ".fitkhata-bridge"),
  pythonBinary: process.env.FITKHATA_ZK_SIDECAR_BIN ?? "python",
  zkPollIntervalMs: Number(process.env.FITKHATA_ZK_POLL_INTERVAL_MS ?? 5_000),
  syncIntervalMs: Number(process.env.FITKHATA_SYNC_INTERVAL_MS ?? 10_000),
  heartbeatIntervalMs: Number(process.env.FITKHATA_HEARTBEAT_INTERVAL_MS ?? 60_000),

  // Turnstile relay -- unset means "no relay board at this install", which
  // is a valid, common configuration (many gyms just log attendance).
  relaySerialPort: process.env.FITKHATA_RELAY_SERIAL_PORT, // e.g. "COM3" or "/dev/ttyUSB0"
  relayDurationMs: Number(process.env.FITKHATA_RELAY_DURATION_MS ?? 3_000),

  // Auto-update -- unset means "no auto-update for this install" (e.g. a
  // dev/test run, or a deployment managed some other way).
  updateRepo: process.env.FITKHATA_UPDATE_REPO, // "owner/name"
  updatePublicKeyHex: process.env.FITKHATA_UPDATE_PUBLIC_KEY_HEX,
  updateCheckIntervalMs: Number(process.env.FITKHATA_UPDATE_CHECK_INTERVAL_MS ?? 6 * 60 * 60_000),
  installPath: process.env.FITKHATA_INSTALL_PATH ?? process.argv[1] ?? "",
};

export function pendingCheckinsPath(): string {
  return join(config.dataDir, "pending-checkins.jsonl");
}
