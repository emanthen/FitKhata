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
import { Apple, CircleCheck, Dumbbell, HeartPulse } from "lucide-react";

import { getCachedPass } from "@/lib/member/pass";
import { cacheWorkoutPlan, getCachedWorkoutPlan } from "@/lib/member/db";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";

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
      <h1 className="flex items-center gap-2 text-xl font-semibold tracking-tight">
        <HeartPulse size={18} strokeWidth={2} className="text-primary" />
        {t("title")}
      </h1>

      <section className="space-y-2">
        <h2 className="text-sm font-medium text-muted-foreground">{t("coachingSuggestionsTitle")}</h2>
        {reports.length === 0 && <p className="text-sm text-muted-foreground">{t("coachingNoSuggestions")}</p>}
        <ul className="space-y-2">
          {reports.map((report) => (
            <li key={report.id}>
              <Card>
                <CardContent className="space-y-1 py-3">
                  <p className="font-dashboard-mono text-xs text-muted-foreground">
                    {t("coachingWeekOf", { date: report.week_start })}
                  </p>
                  {report.suggestions.map((s, i) => (
                    <p key={i} className="text-sm">{s.text_en}</p>
                  ))}
                </CardContent>
              </Card>
            </li>
          ))}
        </ul>
      </section>

      <section className="space-y-2">
        <h2 className="text-sm font-medium text-muted-foreground">{t("coachingQuickLogTitle")}</h2>
        {!selectedExercise ? (
          <div className="grid grid-cols-2 gap-2">
            {exercises.map((ex) => (
              <button
                key={ex.id}
                onClick={() => setSelectedExercise(ex.id)}
                className="rounded-xl border bg-card px-3 py-2.5 text-left text-sm transition-colors hover:bg-muted/60"
              >
                {ex.name_en}
              </button>
            ))}
          </div>
        ) : (
          <Card>
            <CardContent className="space-y-3">
              <div className="flex items-center gap-3">
                <div className="flex-1 space-y-1">
                  <Label htmlFor="log-kg" className="text-xs">{t("coachingKg")}</Label>
                  <Input
                    id="log-kg"
                    type="number"
                    value={kg}
                    onChange={(e) => setKg(Number(e.target.value))}
                    className="h-10"
                  />
                </div>
                <div className="flex-1 space-y-1">
                  <Label htmlFor="log-reps" className="text-xs">{t("coachingReps")}</Label>
                  <Input
                    id="log-reps"
                    type="number"
                    value={reps}
                    onChange={(e) => setReps(Number(e.target.value))}
                    className="h-10"
                  />
                </div>
              </div>
              <Button onClick={logSet} size="lg" className="h-11 w-full">
                {t("coachingSave")}
              </Button>
            </CardContent>
          </Card>
        )}
        {logged && (
          <p className="flex items-center gap-1.5 text-sm text-primary">
            <CircleCheck size={14} strokeWidth={2} />
            {t("coachingLogged")}
          </p>
        )}
      </section>

      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2 text-sm text-muted-foreground">
            <Dumbbell size={15} strokeWidth={2} />
            {t("planWorkoutTitle")}
          </CardTitle>
        </CardHeader>
        <CardContent>
          {planOffline && <p className="mb-2 text-xs text-muted-foreground">{t("planOfflineNotice")}</p>}
          {!workoutPlan ? (
            <p className="text-sm text-muted-foreground">{t("planNoWorkout")}</p>
          ) : (
            <ul className="space-y-2">
              {workoutPlan.days.map((day) => (
                <li key={day.day} className="rounded-lg border p-3 text-sm">
                  <p className="font-medium capitalize">{day.day}</p>
                  <ul className="mt-1 space-y-0.5 text-foreground/80">
                    {day.exercises.map((ex, i) => (
                      <li key={i} data-testid="workout-exercise" className="font-dashboard-mono">
                        {exerciseNames[ex.exercise_id]?.name_en ?? ex.exercise_id} &mdash; {ex.sets}&times;
                        {ex.reps}
                      </li>
                    ))}
                  </ul>
                </li>
              ))}
            </ul>
          )}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2 text-sm text-muted-foreground">
            <Apple size={15} strokeWidth={2} />
            {t("planDietTitle")}
          </CardTitle>
        </CardHeader>
        <CardContent>
          {!dietPlan ? (
            <p className="text-sm text-muted-foreground">{t("planNoDiet")}</p>
          ) : (
            <div className="font-dashboard-mono text-sm">
              <p>{t("planKcalTarget", { count: dietPlan.kcal_target })}</p>
              <p className="text-muted-foreground">{t("planProteinTarget", { count: dietPlan.protein_g })}</p>
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
