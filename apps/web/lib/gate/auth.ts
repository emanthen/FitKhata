/** A paired gate kiosk's own credential — not a user session. Stored
 * separately from token-store.ts's JWT keys since a kiosk isn't a staff
 * login; the raw token here is the device's permanent secret (the server
 * never re-sends it after pairing, see attendance.services.register_gate_device).
 */
export interface DeviceAuth {
  device_id: number;
  gym_id: string;
  token: string;
}

const KEY = "fitkhata.gate.device";

const isBrowser = () => typeof window !== "undefined";

export function getDeviceAuth(): DeviceAuth | null {
  if (!isBrowser()) return null;
  const raw = localStorage.getItem(KEY);
  if (!raw) return null;
  try {
    return JSON.parse(raw) as DeviceAuth;
  } catch {
    return null;
  }
}

export function setDeviceAuth(auth: DeviceAuth): void {
  if (!isBrowser()) return;
  localStorage.setItem(KEY, JSON.stringify(auth));
}

export function clearDeviceAuth(): void {
  if (!isBrowser()) return;
  localStorage.removeItem(KEY);
}
