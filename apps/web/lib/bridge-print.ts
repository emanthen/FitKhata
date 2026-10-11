/** Talks to the local apps/bridge print endpoint (127.0.0.1:7777/print) --
 * FR-3.8/FR-12's hardware bridge. The print token is per-device (the
 * front-desk PC the bridge runs on), not per-org, so it lives in that
 * browser's localStorage, pasted once from the bridge's --pair console
 * output (see apps/bridge/src/pairing.ts) -- there's no backend field for
 * it, deliberately: the backend never needs to know it. */

const STORAGE_KEY = "fitkhata.bridge-print-config";

export interface BridgePrintConfig {
  baseUrl: string; // e.g. http://127.0.0.1:7777
  token: string;
  printerInterface: string; // e.g. "tcp://192.168.1.50" or "printer:USB001"
}

const DEFAULT_BASE_URL = "http://127.0.0.1:7777";

export function getBridgePrintConfig(): BridgePrintConfig | null {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    return raw ? (JSON.parse(raw) as BridgePrintConfig) : null;
  } catch {
    return null;
  }
}

export function setBridgePrintConfig(config: BridgePrintConfig): void {
  localStorage.setItem(STORAGE_KEY, JSON.stringify(config));
}

export function clearBridgePrintConfig(): void {
  localStorage.removeItem(STORAGE_KEY);
}

export interface ReceiptLine {
  label: string;
  value: string;
}

export interface PrintReceiptInput {
  gymName: string;
  titleNe: string;
  lines: ReceiptLine[];
  totalNpr: string;
}

/** Throws if no bridge is configured in this browser, or the bridge
 * rejects/fails the print -- callers should catch and fall back to the
 * existing PDF/SMS receipt paths, never block the invoice flow on a
 * printer being reachable. */
export async function printReceiptViaBridge(input: PrintReceiptInput): Promise<void> {
  const config = getBridgePrintConfig();
  if (!config) throw new Error("No printer configured on this device.");

  const res = await fetch(`${config.baseUrl ?? DEFAULT_BASE_URL}/print`, {
    method: "POST",
    headers: { "content-type": "application/json", authorization: `Bearer ${config.token}` },
    body: JSON.stringify({
      template: "receipt",
      printerInterface: config.printerInterface,
      ...input,
    }),
  });
  if (!res.ok) {
    const body = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(body.detail ?? "Print failed.");
  }
}
