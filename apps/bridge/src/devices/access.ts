import type { SnapshotMember } from "../types.js";

/** Local allow/deny for turnstile relay firing -- "validation runs locally
 * ALWAYS" (same principle the gate kiosk PWA's lib/gate-validate.ts
 * follows), since a biometric match happens at the door, not after a
 * server round-trip. Deliberately coarser than the kiosk's full green/
 * amber/red classification (attendance.services.classify_checkin) or the
 * server's own record_checkins_batch (which doesn't re-validate at all,
 * trusting the device) -- this only decides "open the gate or not", not
 * the full accounting the server does. ponytail ceiling: no access-hours
 * or outstanding-dues check yet (those need the full snapshot payload,
 * not just status/expiry_date) -- add them if a gym actually needs the
 * gate to enforce them locally rather than just logging the visit. */
export function isCheckinAllowed(member: SnapshotMember, now: Date): boolean {
  if (member.status !== "active" && member.status !== "trial") return false;
  if (!member.expiry_date) return true;
  const today = now.toISOString().slice(0, 10);
  return member.expiry_date >= today;
}
