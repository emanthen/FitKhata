/** Offline cache for the member's own assigned workout plan (FR-8.5).
 * Separate Dexie database from the gate kiosk's "fitkhata-gate" (lib/gate/
 * db.ts): that one is kiosk-device-scoped (keyed by device pairing) and
 * shared-device roster data worth encrypting at rest; this one is the
 * member's own device/identity and holds nothing more sensitive than
 * exercise names, so no crypto layer is needed here.
 */
import Dexie, { type Table } from "dexie";
import type { WorkoutPlan } from "@fitkhata/api-client";

interface CachedWorkoutPlanRow {
  member_code: string; // primary key — one row per member, this device
  plan: WorkoutPlan;
  exercise_names: Record<string, { name_en: string; name_ne: string }>;
  cached_at: string;
}

class MemberDb extends Dexie {
  workoutPlan!: Table<CachedWorkoutPlanRow, string>;

  constructor() {
    super("fitkhata-member");
    this.version(1).stores({ workoutPlan: "member_code" });
  }
}

export const memberDb = new MemberDb();

export async function cacheWorkoutPlan(
  memberCode: string,
  plan: WorkoutPlan,
  exerciseNames: Record<string, { name_en: string; name_ne: string }>
): Promise<void> {
  await memberDb.workoutPlan.put({
    member_code: memberCode,
    plan,
    exercise_names: exerciseNames,
    cached_at: new Date().toISOString(),
  });
}

export async function getCachedWorkoutPlan(
  memberCode: string
): Promise<CachedWorkoutPlanRow | null> {
  return (await memberDb.workoutPlan.get(memberCode)) ?? null;
}
