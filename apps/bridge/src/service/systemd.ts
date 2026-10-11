import { execFileSync } from "node:child_process";
import { copyFileSync } from "node:fs";
import { fileURLToPath } from "node:url";

const UNIT_NAME = "fitkhata-bridge.service";
const UNIT_DEST = `/etc/systemd/system/${UNIT_NAME}`;

/** Installs and enables the systemd unit for Raspberry Pi deployments.
 * Requires root (install scripts run via sudo); not invoked on Windows. */
export function installSystemdService(): void {
  const unitSource = fileURLToPath(new URL("../../systemd/fitkhata-bridge.service", import.meta.url));
  copyFileSync(unitSource, UNIT_DEST);
  execFileSync("systemctl", ["daemon-reload"]);
  execFileSync("systemctl", ["enable", "--now", UNIT_NAME]);
}

export function uninstallSystemdService(): void {
  execFileSync("systemctl", ["disable", "--now", UNIT_NAME]);
}

export function restartSystemdService(): void {
  execFileSync("systemctl", ["restart", UNIT_NAME]);
}
