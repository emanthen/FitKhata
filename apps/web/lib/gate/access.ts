/** TS port of apps/api/members/domain/access.py's is_within_access_hours —
 * same Plan.access_hours JSON schema, same semantics. Must stay a pure
 * function with no network/Dexie access: the gate's local validation runs
 * entirely offline in <500ms.
 *
 * Schema:
 *   {}                               -> unrestricted (default)
 *   {"always": true}                 -> unrestricted, explicit
 *   {"windows": [{"day": "mon", "start": "06:00", "end": "22:00"}, ...]}
 *     -> restricted to the union of listed day/time windows. "day" is a
 *     lowercase 3-letter code (mon..sun); "start"/"end" are "HH:MM",
 *     inclusive both ends, same-day only.
 */

const DAY_CODES = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"] as const;

interface AccessWindow {
  day: string;
  start: string;
  end: string;
}

export interface AccessHours {
  always?: boolean;
  windows?: AccessWindow[];
}

function toMinutes(hhmm: string): number {
  const [h, m] = hhmm.split(":").map(Number);
  return h * 60 + m;
}

export function isWithinAccessHours(accessHours: AccessHours, nowKathmandu: Date): boolean {
  const windows = accessHours.windows;
  if (!windows || windows.length === 0) return true;

  // getDay(): 0=Sun..6=Sat; DAY_CODES is mon-indexed-0, so shift by one.
  const dayCode = DAY_CODES[(nowKathmandu.getDay() + 6) % 7];
  const currentMinutes = nowKathmandu.getHours() * 60 + nowKathmandu.getMinutes();

  for (const window of windows) {
    if (window.day !== dayCode) continue;
    const start = toMinutes(window.start);
    const end = toMinutes(window.end);
    if (currentMinutes >= start && currentMinutes <= end) return true;
  }
  return false;
}
