/** Local, offline, <500ms green/amber/red decision — mirrors
 * apps/api/attendance/services.py's classify_checkin + its anti-passback
 * check, run entirely against the cached CachedMember record (see db.ts).
 * No network, no Dexie writes here: this is a pure function so it's cheap
 * to unit test and cheap to call on every scan.
 */
import { isWithinAccessHours } from "./access";
import type { CachedMember } from "./db";

export type Classification = "green" | "amber" | "red";

const AMBER_THRESHOLD_DAYS = 3;
// ponytail: a fixed default rather than per-gym — GateSnapshotView's
// payload doesn't include gym.settings.anti_passback_min, only per-member
// fields. Mirrors the backend's own fallback default
// (attendance/services.py's `gym.settings.get("anti_passback_min", 5)`).
// Upgrade path: add anti_passback_min to the snapshot payload once a gym
// actually needs a non-default window.
const ANTI_PASSBACK_MIN_MINUTES = 5;

const BLOCKED_STATUSES = new Set(["expired", "frozen", "cancelled"]);

function dateOnly(d: Date): Date {
  return new Date(d.getFullYear(), d.getMonth(), d.getDate());
}

function daysBetween(from: Date, to: Date): number {
  const MS_PER_DAY = 24 * 60 * 60 * 1000;
  return Math.round((dateOnly(to).getTime() - dateOnly(from).getTime()) / MS_PER_DAY);
}

export function classifyCheckin(member: CachedMember, now: Date): Classification {
  if (BLOCKED_STATUSES.has(member.status)) return "red";
  if (Number(member.dues_npr) > 0) return "red";

  if (member.local_last_check_in_at) {
    const minutesSinceLast =
      (now.getTime() - new Date(member.local_last_check_in_at).getTime()) / 60_000;
    if (minutesSinceLast < ANTI_PASSBACK_MIN_MINUTES) return "red";
  }

  if (member.expiry_date) {
    const expiry = new Date(`${member.expiry_date}T00:00:00`);
    const daysLeft = daysBetween(now, expiry);
    if (daysLeft < 0) return "red";
    if (daysLeft <= AMBER_THRESHOLD_DAYS) return "amber";
    if (!isWithinAccessHours(member.access_hours, now)) return "red";
  }

  return "green";
}
