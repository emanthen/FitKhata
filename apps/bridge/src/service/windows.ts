// @ts-expect-error -- node-windows ships no types
import { Service } from "node-windows";

const SERVICE_NAME = "FitKhata Bridge";
const SERVICE_DESCRIPTION =
  "FitKhata gate hardware bridge: ZKTeco check-ins, turnstile, receipt printing.";

function buildService(scriptPath: string): Service {
  return new Service({
    name: SERVICE_NAME,
    description: SERVICE_DESCRIPTION,
    script: scriptPath,
  });
}

export function installWindowsService(scriptPath: string): Promise<void> {
  return new Promise((resolve, reject) => {
    const svc = buildService(scriptPath);
    svc.on("install", () => {
      svc.start();
      resolve();
    });
    svc.on("alreadyinstalled", () => resolve());
    svc.on("error", reject);
    svc.install();
  });
}

export function uninstallWindowsService(scriptPath: string): Promise<void> {
  return new Promise((resolve, reject) => {
    const svc = buildService(scriptPath);
    svc.on("uninstall", () => resolve());
    svc.on("error", reject);
    svc.uninstall();
  });
}

export function restartWindowsService(scriptPath: string): void {
  const svc = buildService(scriptPath);
  svc.restart();
}
