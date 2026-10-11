import { createServer } from "node:http";

import type { BridgeApiConfig } from "./api-client.js";
import { getSnapshot, postCheckinsBatch } from "./api-client.js";
import { config, pendingCheckinsPath } from "./config.js";
import { isCheckinAllowed } from "./devices/access.js";
import { openCashDrawer, printReceipt, type ReceiptData } from "./devices/escpos.js";
import { openSerialRelayDriver, triggerRelay, type RelayDriver } from "./devices/relay.js";
import { pollAttendanceOnce, spawnZkSidecar, syncEnrollment } from "./devices/zkteco.js";
import { startHeartbeatLoop } from "./health/heartbeat.js";
import { createPrintServer } from "./http/print-server.js";
import { OfflineQueue } from "./offline-queue.js";
import { pairAndStore } from "./pairing.js";
import { SecureStore } from "./secure-store.js";
import type { SnapshotMember } from "./types.js";
import { checkForUpdate, downloadAndVerify } from "./update/auto-update.js";
import { flushOnce, startSyncLoop } from "./sync-loop.js";

async function runPairingCommand(code: string, deviceName: string): Promise<void> {
  const store = new SecureStore(config.dataDir);
  await pairAndStore(config.apiBaseUrl, code, deviceName, store);
}

async function runServiceCommand(action: "install" | "uninstall"): Promise<void> {
  const scriptPath = config.installPath;
  if (process.platform === "win32") {
    const { installWindowsService, uninstallWindowsService } = await import(
      "./service/windows.js"
    );
    await (action === "install"
      ? installWindowsService(scriptPath)
      : uninstallWindowsService(scriptPath));
  } else {
    const { installSystemdService, uninstallSystemdService } = await import(
      "./service/systemd.js"
    );
    action === "install" ? installSystemdService() : uninstallSystemdService();
  }
  console.log(`Service ${action} complete.`);
}

function startHealthzServer(): void {
  createServer((req, res) => {
    if (req.url === "/healthz") {
      res.writeHead(200, { "content-type": "application/json" });
      res.end(JSON.stringify({ status: "ok" }));
      return;
    }
    res.writeHead(404).end();
  }).listen(config.healthzPort, () => {
    console.log(`fitkhata-bridge healthz listening on :${config.healthzPort}`);
  });
}

interface PrintRequestBody {
  template: "receipt" | "drawer-close";
  printerInterface: string;
  gymName?: string;
  titleNe?: string;
  lines?: ReceiptData["lines"];
  totalNpr?: string;
}

async function handlePrintRequest(body: unknown): Promise<void> {
  const req = body as PrintRequestBody;
  if (!req.printerInterface) throw new Error("printerInterface is required");

  if (req.template === "drawer-close") {
    await openCashDrawer({ interface: req.printerInterface });
    return;
  }
  await printReceipt(
    { interface: req.printerInterface },
    {
      gymName: req.gymName ?? "",
      titleNe: req.titleNe ?? "",
      lines: req.lines ?? [],
      totalNpr: req.totalNpr ?? "",
    }
  );
}

/** Refreshes the device user_id -> member snapshot map from /gate/snapshot,
 * and pushes each changed member's enrolment state to the ZK device to
 * match (see zkteco.ts::syncEnrollment). Enrolment convention (per the
 * spec): a member's ZK device user_id is their numeric member_id. */
async function refreshSnapshot(
  apiConfig: BridgeApiConfig,
  zkClient: ReturnType<typeof spawnZkSidecar> | null,
  map: Map<string, SnapshotMember>
): Promise<void> {
  const snapshot = await getSnapshot(apiConfig);
  for (const member of snapshot.members) {
    const deviceUserId = String(member.member_id);
    map.set(deviceUserId, member);
    if (zkClient) {
      await syncEnrollment(zkClient, member).catch((err) =>
        console.error(`enrolment sync failed for member ${member.member_code}:`, err)
      );
    }
  }
}

async function startZkIntegration(
  apiConfig: BridgeApiConfig,
  queue: OfflineQueue,
  relayDriver: RelayDriver | null
): Promise<void> {
  const zkHost = process.env.FITKHATA_ZK_HOST;
  if (!zkHost) {
    console.log("FITKHATA_ZK_HOST not set -- skipping ZKTeco integration for this run.");
    return;
  }
  const zkPort = Number(process.env.FITKHATA_ZK_PORT ?? 4370);

  const client = spawnZkSidecar(config.pythonBinary);
  await client.connect(zkHost, zkPort);

  const membersByDeviceUserId = new Map<string, SnapshotMember>();
  await refreshSnapshot(apiConfig, client, membersByDeviceUserId);
  setInterval(() => {
    refreshSnapshot(apiConfig, client, membersByDeviceUserId).catch((err) =>
      console.error("snapshot refresh failed:", err)
    );
  }, 60_000);

  let offset = 0;
  setInterval(() => {
    pollAttendanceOnce(
      client,
      offset,
      (userId) => membersByDeviceUserId.get(userId)?.member_code,
      (row) => {
        queue.enqueue(row);

        if (relayDriver) {
          const member = [...membersByDeviceUserId.values()].find(
            (m) => m.member_code === row.member_code
          );
          if (member && isCheckinAllowed(member, new Date())) {
            triggerRelay(relayDriver, config.relayDurationMs).catch((err) =>
              console.error("relay trigger failed:", err)
            );
          }
        }
      }
    )
      .then((nextOffset) => {
        offset = nextOffset;
      })
      .catch((err) => console.error("ZK attendance poll failed:", err));
  }, config.zkPollIntervalMs);
}

function startAutoUpdateLoop(): void {
  if (!config.updateRepo || !config.updatePublicKeyHex) {
    console.log("Auto-update not configured for this run -- skipping.");
    return;
  }
  const updateConfig = {
    repo: config.updateRepo,
    currentVersion: process.env.FITKHATA_BRIDGE_VERSION ?? "0.1.0",
    publicKeyHex: config.updatePublicKeyHex,
    installPath: config.installPath,
  };
  const assetSuffix = process.platform === "win32" ? "-win.exe" : "-linux-arm64";

  const check = async () => {
    try {
      const release = await checkForUpdate(updateConfig);
      if (!release) return;
      console.log(`New release ${release.tag_name} found -- downloading and verifying...`);
      await downloadAndVerify(updateConfig, release, assetSuffix);
      console.log("Update installed. Restart the service to apply it.");
    } catch (err) {
      console.error("auto-update check failed:", err);
    }
  };
  void check();
  setInterval(check, config.updateCheckIntervalMs);
}

async function main(): Promise<void> {
  const args = process.argv.slice(2);
  if (args[0] === "--pair") {
    const [, code, deviceName] = args;
    if (!code || !deviceName) {
      console.error("Usage: fitkhata-bridge --pair <code> <device-name>");
      process.exit(1);
    }
    await runPairingCommand(code, deviceName);
    return;
  }
  if (args[0] === "--install-service" || args[0] === "--uninstall-service") {
    await runServiceCommand(args[0] === "--install-service" ? "install" : "uninstall");
    return;
  }

  const store = new SecureStore(config.dataDir);
  const creds = await store.load();
  if (!creds) {
    console.error(
      "No paired device found. Run with --pair <code> <device-name> first (code comes from the gym's admin console)."
    );
    process.exit(1);
  }

  const apiConfig: BridgeApiConfig = { baseUrl: config.apiBaseUrl, deviceToken: creds.deviceToken };
  const queue = new OfflineQueue(pendingCheckinsPath());

  startHealthzServer();
  startHeartbeatLoop(apiConfig, config.heartbeatIntervalMs);
  startSyncLoop(queue, (rows) => postCheckinsBatch(apiConfig, rows), config.syncIntervalMs);
  void flushOnce(queue, (rows) => postCheckinsBatch(apiConfig, rows)); // drain anything left from a prior crash immediately
  startAutoUpdateLoop();

  createPrintServer(
    { webOrigin: config.webOrigin, printToken: creds.printToken },
    handlePrintRequest
  ).listen(config.printPort, () => {
    console.log(`fitkhata-bridge print endpoint listening on 127.0.0.1:${config.printPort}`);
  });

  const relayDriver = config.relaySerialPort
    ? await openSerialRelayDriver(config.relaySerialPort)
    : null;
  await startZkIntegration(apiConfig, queue, relayDriver);
}

main().catch((err) => {
  console.error(err);
  process.exit(1);
});
