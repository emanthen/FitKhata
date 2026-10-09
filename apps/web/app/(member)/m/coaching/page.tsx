"use client";

import { useEffect, useState } from "react";
import { useTranslations } from "next-intl";
import {
  getMemberPlan,
  listExercises,
  listMemberCoachingReports,
  memberQuickLog,
  type CoachingReport,
  type DietPlan,
  type Exercise,
  type WorkoutPlan,
} from "@fitkhata/api-client";

import { getCachedPass } from "@/lib/member/pass";
import { cacheWorkoutPlan, getCachedWorkoutPlan } from "@/lib/member/db";

export default function MemberCoachingPage() {
  const t = useTranslations("member");
  const [reports, setReports] = useState<CoachingReport[]>([]);
  const [exercises, setExercises] = useState<Exercise[]>([]);
  const [selectedExercise, setSelectedExercise] = useState<string | null>(null);
  const [kg, setKg] = useState(20);
  const [reps, setReps] = useState(10);
  const [logged, setLogged] = useState(false);
  const [workoutPlan, setWorkoutPlan] = useState<WorkoutPlan | null>(null);
  const [dietPlan, setDietPlan] = useState<DietPlan | null>(null);
  const [exerciseNames, setExerciseNames] = useState<
    Record<string, { name_en: string; name_ne: string }>
  >({});
  const [planOffline, setPlanOffline] = useState(false);

  useEffect(() => {
    const pass = getCachedPass();
    if (!pass) return;
    listMemberCoachingReports(pass.token).then(setReports).catch(() => setReports([]));

    listExercises().then(async (data) => {
      const list = Array.isArray(data) ? data : data.results;
      setExercises(list.slice(0, 8)); // a short pick-list, not the full 300
      const namesById = Object.fromEntries(
        list.map((ex) => [ex.id, { name_en: ex.name_en, name_ne: ex.name_ne }])
      );
      setExerciseNames(namesById);

      try {
        const { workout_plan, diet_plan } = await getMemberPlan(pass.token);
        setWorkoutPlan(workout_plan);
        setDietPlan(diet_plan);
        if (workout_plan) await cacheWorkoutPlan(pass.member_code, workout_plan, namesById);
      } catch {
        const cached = await getCachedWorkoutPlan(pass.member_code);
        if (cached) {
          setWorkoutPlan(cached.plan);
          setExerciseNames(cached.exercise_names);
          setPlanOffline(true);
        }
      }
    });
  }, []);

  // Tap 1: pick an exercise. Tap 2: adjust prefilled kg/reps if needed.
  // Tap 3: save. Defaults are prefilled so most logs need only tap 1 + save.
  async function logSet() {
    const pass = getCachedPass();
    if (!pass || !selectedExercise) return;
    await memberQuickLog(pass.token, { exercise: selectedExercise, sets: [{ kg, reps }] });
    setLogged(true);
    setSelectedExercise(null);
  }

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-semibold">{t("title")}</h1>

      <section className="space-y-2">
        <h2 className="text-lg font-medium">{t("coachingSuggestionsTitle")}</h2>
        {reports.length === 0 && <p className="text-sm opacity-60">{t("coachingNoSuggestions")}</p>}
        <ul className="space-y-2">
          {reports.map((report) => (
            <li key={report.id} className="space-y-1 rounded border p-3 text-sm">
              <p className="opacity-60">{t("coachingWeekOf", { date: report.week_start })}</p>
              {report.suggestions.map((s, i) => (
                <p key={i}>{s.text_en}</p>
              ))}
            </li>
          ))}
        </ul>
      </section>

      <section className="space-y-2">
        <h2 className="text-lg font-medium">{t("coachingQuickLogTitle")}</h2>
        {!selectedExercise ? (
          <div className="grid grid-cols-2 gap-2">
            {exercises.map((ex) => (
              <button
                key={ex.id}
                onClick={() => setSelectedExercise(ex.id)}
                className="rounded border px-3 py-2 text-left text-sm hover:bg-muted"
              >
                {ex.name_en}
              </button>
            ))}
          </div>
        ) : (
          <div className="space-y-2 rounded border p-3">
            <div className="flex items-center gap-3">
              <label className="text-sm">
                {t("coachingKg")}
                <input
                  type="number"
                  value={kg}
                  onChange={(e) => setKg(Number(e.target.value))}
                  className="ml-2 h-8 w-16 rounded border px-2"
                />
              </label>
              <label className="text-sm">
                {t("coachingReps")}
                <input
                  type="number"
                  value={reps}
                  onChange={(e) => setReps(Number(e.target.value))}
                  className="ml-2 h-8 w-16 rounded border px-2"
                />
              </label>
            </div>
            <button
              onClick={logSet}
              className="w-full rounded bg-black px-3 py-2 text-sm text-white"
            >
              {t("coachingSave")}
            </button>
          </div>
        )}
        {logged && <p className="text-sm text-green-700">{t("coachingLogged")}</p>}
      </section>

      <section className="space-y-2">
        <h2 className="text-lg font-medium">{t("planWorkoutTitle")}</h2>
        {planOffline && <p className="text-xs opacity-60">{t("planOfflineNotice")}</p>}
        {!workoutPlan ? (
          <p className="text-sm opacity-60">{t("planNoWorkout")}</p>
        ) : (
          <ul className="space-y-2">
            {workoutPlan.days.map((day) => (
              <li key={day.day} className="rounded border p-3 text-sm">
                <p className="font-medium capitalize">{day.day}</p>
                <ul className="mt-1 space-y-0.5 opacity-80">
                  {day.exercises.map((ex, i) => (
                    <li key={i} data-testid="workout-exercise">
                      {exerciseNames[ex.exercise_id]?.name_en ?? ex.exercise_id} — {ex.sets}×
                      {ex.reps}
                    </li>
                  ))}
                </ul>
              </li>
            ))}
          </ul>
        )}
      </section>

      <section className="space-y-2">
        <h2 className="text-lg font-medium">{t("planDietTitle")}</h2>
        {!dietPlan ? (
          <p className="text-sm opacity-60">{t("planNoDiet")}</p>
        ) : (
          <div className="rounded border p-3 text-sm">
            <p>{t("planKcalTarget", { count: dietPlan.kcal_target })}</p>
            <p className="opacity-70">{t("planProteinTarget", { count: dietPlan.protein_g })}</p>
          </div>
        )}
      </section>
    </div>
  );
}
