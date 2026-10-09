import { httpClient } from "./http-client";
import type { Page } from "./members";

// --- Global catalogs -----------------------------------------------------

export type MuscleGroup =
  | "chest"
  | "back"
  | "shoulders"
  | "biceps"
  | "triceps"
  | "legs"
  | "glutes"
  | "core"
  | "cardio";
export type Equipment =
  | "barbell"
  | "dumbbell"
  | "machine"
  | "bodyweight"
  | "cable"
  | "band"
  | "kettlebell";

export interface Exercise {
  id: string;
  name_en: string;
  name_ne: string;
  muscle_group: MuscleGroup;
  equipment: Equipment;
  media_url: string;
  is_active: boolean;
}

export interface FoodItem {
  id: string;
  name_en: string;
  name_ne: string;
  kcal_per_100g: string;
  protein_g_per_100g: string;
  carbs_g_per_100g: string;
  fat_g_per_100g: string;
}

export const listExercises = (params?: {
  muscle_group?: MuscleGroup;
  equipment?: Equipment;
}): Promise<Exercise[] | Page<Exercise>> =>
  httpClient({ method: "GET", url: "/api/v1/coaching/exercises/", params });

export const listFoodItems = (): Promise<FoodItem[] | Page<FoodItem>> =>
  httpClient({ method: "GET", url: "/api/v1/coaching/food-items/" });

// --- Client profiles -------------------------------------------------------

export type CoachingGoal =
  | "weight_loss"
  | "weight_gain"
  | "muscle_gain"
  | "general_fitness"
  | "endurance";

export interface ClientProfile {
  id: string;
  member: string;
  member_name: string;
  trainer: string | null;
  primary_goal: CoachingGoal;
  starting_weight_kg: string;
  target_weight_kg: string;
  workout_plan: string | null;
  diet_plan: string | null;
  coach_notes: string;
  consent_health_data: boolean;
  consent_at: string | null;
  created_at: string;
}

export const listClientProfiles = (): Promise<ClientProfile[] | Page<ClientProfile>> =>
  httpClient({ method: "GET", url: "/api/v1/coaching/client-profiles/" });

export const createClientProfile = (data: {
  member: string;
  trainer?: string;
  primary_goal: CoachingGoal;
  starting_weight_kg: string;
  target_weight_kg: string;
}): Promise<ClientProfile> =>
  httpClient({ method: "POST", url: "/api/v1/coaching/client-profiles/", data });

export const updateClientProfile = (
  id: string,
  data: Partial<ClientProfile>
): Promise<ClientProfile> =>
  httpClient({ method: "PATCH", url: `/api/v1/coaching/client-profiles/${id}/`, data });

export interface ClientProgress {
  goal_progress_pct: number;
  attendance_pct: number;
  current_weight_kg: number;
}

export const getClientProgress = (profileId: string): Promise<ClientProgress> =>
  httpClient({ method: "GET", url: `/api/v1/coaching/client-profiles/${profileId}/progress/` });

// --- Body measurements -------------------------------------------------------

export interface BodyMeasurementPhoto {
  id: string;
  angle: "front" | "side" | "back" | "";
  url: string;
}

export interface BodyMeasurement {
  id: string;
  member: string;
  measured_on: string;
  weight_kg: string;
  body_fat_pct: string | null;
  measurements: Record<string, number>;
  photos: BodyMeasurementPhoto[];
  created_at: string;
}

export const listMeasurements = (memberId: string): Promise<BodyMeasurement[] | Page<BodyMeasurement>> =>
  httpClient({ method: "GET", url: "/api/v1/coaching/measurements/", params: { member: memberId } });

export const recordMeasurement = (data: FormData): Promise<BodyMeasurement> =>
  httpClient({
    method: "POST",
    url: "/api/v1/coaching/measurements/",
    data,
    headers: { "Content-Type": "multipart/form-data" },
  });

// --- Diet logs ---------------------------------------------------------------

export const logProteinIntake = (data: {
  member: string;
  logged_on: string;
  protein_g: string;
}): Promise<{ id: string }> => httpClient({ method: "POST", url: "/api/v1/coaching/diet-logs/", data });

// --- Plans ---------------------------------------------------------------------

export type WorkoutSplit = "ppl" | "upper_lower" | "full_body" | "custom";

export interface WorkoutPlanExercise {
  exercise_id: string;
  sets: number;
  reps: number;
  rest_s: number;
}

export interface WorkoutPlanDay {
  day: string;
  exercises: WorkoutPlanExercise[];
}

export interface WorkoutPlan {
  id: string;
  name: string;
  split: WorkoutSplit;
  days: WorkoutPlanDay[];
  created_at: string;
}

export const listWorkoutPlans = (): Promise<WorkoutPlan[] | Page<WorkoutPlan>> =>
  httpClient({ method: "GET", url: "/api/v1/coaching/workout-plans/" });

export const createWorkoutPlan = (data: {
  name: string;
  split: WorkoutSplit;
  days: WorkoutPlanDay[];
}): Promise<WorkoutPlan> => httpClient({ method: "POST", url: "/api/v1/coaching/workout-plans/", data });

export interface DietPlanMealItem {
  food_item_id: string;
  grams: number;
}

export interface DietPlanMeal {
  meal: string;
  items: DietPlanMealItem[];
}

export interface DietPlan {
  id: string;
  name: string;
  kcal_target: number;
  protein_g: string;
  meals: DietPlanMeal[];
  created_at: string;
}

export const listDietPlans = (): Promise<DietPlan[] | Page<DietPlan>> =>
  httpClient({ method: "GET", url: "/api/v1/coaching/diet-plans/" });

export const createDietPlan = (data: {
  name: string;
  kcal_target: number;
  protein_g: string;
  meals: DietPlanMeal[];
}): Promise<DietPlan> => httpClient({ method: "POST", url: "/api/v1/coaching/diet-plans/", data });

// --- Workout logs (quick logger) ---------------------------------------------

export interface WorkoutSet {
  kg: number;
  reps: number;
}

export interface WorkoutLog {
  id: string;
  member: string;
  logged_on: string;
  exercise: string;
  exercise_name_en: string;
  sets: WorkoutSet[];
  created_at: string;
}

export const listWorkoutLogs = (memberId: string): Promise<WorkoutLog[] | Page<WorkoutLog>> =>
  httpClient({ method: "GET", url: "/api/v1/coaching/workout-logs/", params: { member: memberId } });

export const logWorkout = (data: {
  member: string;
  exercise: string;
  logged_on?: string;
  sets: WorkoutSet[];
}): Promise<WorkoutLog> => httpClient({ method: "POST", url: "/api/v1/coaching/workout-logs/", data });

// --- PT packs + sessions -------------------------------------------------------

export interface PTPack {
  id: string;
  member: string;
  trainer: string | null;
  sessions_total: number;
  sessions_used: number;
  price_npr: string;
  expires_on: string;
  created_at: string;
}

export const listPTPacks = (): Promise<PTPack[] | Page<PTPack>> =>
  httpClient({ method: "GET", url: "/api/v1/coaching/pt-packs/" });

export const createPTPack = (data: {
  member: string;
  trainer?: string;
  sessions_total: number;
  price_npr: string;
  expires_on: string;
}): Promise<PTPack> => httpClient({ method: "POST", url: "/api/v1/coaching/pt-packs/", data });

export interface PTSession {
  id: string;
  pack: string;
  scheduled_at: string;
  attended: boolean;
}

export const listPTSessions = (): Promise<PTSession[] | Page<PTSession>> =>
  httpClient({ method: "GET", url: "/api/v1/coaching/pt-sessions/" });

export const createPTSession = (data: { pack: string; scheduled_at: string }): Promise<PTSession> =>
  httpClient({ method: "POST", url: "/api/v1/coaching/pt-sessions/", data });

export const markPTSessionAttended = (
  id: string,
  attended: boolean
): Promise<PTSession> =>
  httpClient({
    method: "POST",
    url: `/api/v1/coaching/pt-sessions/${id}/mark_attended/`,
    data: { attended },
  });

// --- Classes + bookings -------------------------------------------------------

export interface ClassSchedule {
  id: string;
  name: string;
  trainer: string | null;
  starts_at: string;
  capacity: number;
  booked_count: number;
  created_at: string;
}

export const listClassSchedules = (): Promise<ClassSchedule[] | Page<ClassSchedule>> =>
  httpClient({ method: "GET", url: "/api/v1/coaching/classes/" });

export const createClassSchedule = (data: {
  name: string;
  trainer?: string;
  starts_at: string;
  capacity: number;
}): Promise<ClassSchedule> => httpClient({ method: "POST", url: "/api/v1/coaching/classes/", data });

export type ClassBookingStatus = "booked" | "waitlist" | "cancelled" | "attended";

export interface ClassBooking {
  id: string;
  class_schedule: string;
  member: string;
  member_name: string;
  status: ClassBookingStatus;
  created_at: string;
}

export const listClassBookings = (classScheduleId?: string): Promise<ClassBooking[] | Page<ClassBooking>> =>
  httpClient({
    method: "GET",
    url: "/api/v1/coaching/bookings/",
    params: classScheduleId ? { class_schedule: classScheduleId } : undefined,
  });

export const bookClass = (data: { class_schedule: string; member: string }): Promise<ClassBooking> =>
  httpClient({ method: "POST", url: "/api/v1/coaching/bookings/", data });

export const cancelBooking = (id: string): Promise<ClassBooking> =>
  httpClient({ method: "POST", url: `/api/v1/coaching/bookings/${id}/cancel/` });

// --- Coaching reports ----------------------------------------------------------

export interface CoachingSuggestion {
  type: "workout" | "diet" | "recovery" | "attendance" | "general";
  text_en: string;
  text_ne: string;
  reason: string;
}

export interface CoachingReport {
  id: string;
  member: string | null;
  member_name: string;
  week_start: string;
  kind: "member" | "branch";
  flags: unknown;
  suggestions: CoachingSuggestion[];
  status: "draft" | "approved" | "rejected";
  approved_by: string | null;
  approved_at: string | null;
  model: string;
  tokens_used: number;
  cost_npr: string;
  created_at: string;
}

export const listCoachingReports = (filters?: {
  kind?: "member" | "branch";
  status?: string;
}): Promise<CoachingReport[] | Page<CoachingReport>> =>
  httpClient({ method: "GET", url: "/api/v1/coaching/reports/", params: filters });

export const approveCoachingReport = (id: string): Promise<CoachingReport> =>
  httpClient({ method: "POST", url: `/api/v1/coaching/reports/${id}/approve/` });

export const rejectCoachingReport = (id: string, reason?: string): Promise<CoachingReport> =>
  httpClient({ method: "POST", url: `/api/v1/coaching/reports/${id}/reject/`, data: { reason } });

// --- Dashboards ----------------------------------------------------------------

export const getTrainerDashboard = (): Promise<{
  clients: ClientProfile[];
  pending_approvals: CoachingReport[];
}> => httpClient({ method: "GET", url: "/api/v1/coaching/dashboard" });

export const getOwnerCoachingInsights = (): Promise<{
  latest_branch_report: CoachingReport | null;
  ai_budget_npr_monthly: number;
  ai_spend_npr_month_to_date: string;
}> => httpClient({ method: "GET", url: "/api/v1/coaching/insights" });

// --- Member-facing (token-authenticated) --------------------------------------

export const listMemberCoachingReports = (passToken: string): Promise<CoachingReport[]> =>
  httpClient({ method: "GET", url: `/api/v1/m/pass/${passToken}/coaching/reports` });

export const memberQuickLog = (
  passToken: string,
  data: { exercise: string; sets: WorkoutSet[] }
): Promise<WorkoutLog> =>
  httpClient({ method: "POST", url: `/api/v1/m/pass/${passToken}/coaching/log`, data });

export const getMemberPlan = (
  passToken: string
): Promise<{ workout_plan: WorkoutPlan | null; diet_plan: DietPlan | null }> =>
  httpClient({ method: "GET", url: `/api/v1/m/pass/${passToken}/coaching/plan` });

export const getMemberNextClass = (
  passToken: string
): Promise<{ class_name: string; starts_at: string } | null> =>
  httpClient({ method: "GET", url: `/api/v1/m/pass/${passToken}/next-class` });

export const listMemberClasses = (passToken: string): Promise<ClassSchedule[]> =>
  httpClient({ method: "GET", url: `/api/v1/m/pass/${passToken}/classes` });

export const bookMemberClass = (
  passToken: string,
  scheduleId: string
): Promise<ClassBooking> =>
  httpClient({
    method: "POST",
    url: `/api/v1/m/pass/${passToken}/classes/${scheduleId}/book`,
  });

export const cancelMemberBooking = (
  passToken: string,
  bookingId: string
): Promise<ClassBooking> =>
  httpClient({
    method: "POST",
    url: `/api/v1/m/pass/${passToken}/bookings/${bookingId}/cancel`,
  });
