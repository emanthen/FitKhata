"use client";

import { useState } from "react";
import { useTranslations } from "next-intl";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import {
  createWorkoutPlan,
  listExercises,
  listWorkoutPlans,
  type WorkoutPlanDay,
  type WorkoutPlanExercise,
  type WorkoutSplit,
} from "@fitkhata/api-client";
import { Dumbbell } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";

const DAYS = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"] as const;
const DAY_KEYS: Record<(typeof DAYS)[number], string> = {
  mon: "coachingWorkoutDayMon",
  tue: "coachingWorkoutDayTue",
  wed: "coachingWorkoutDayWed",
  thu: "coachingWorkoutDayThu",
  fri: "coachingWorkoutDayFri",
  sat: "coachingWorkoutDaySat",
  sun: "coachingWorkoutDaySun",
};
const SPLITS: { value: WorkoutSplit; labelKey: string }[] = [
  { value: "ppl", labelKey: "coachingWorkoutSplitPpl" },
  { value: "upper_lower", labelKey: "coachingWorkoutSplitUpperLower" },
  { value: "full_body", labelKey: "coachingWorkoutSplitFullBody" },
  { value: "custom", labelKey: "coachingWorkoutSplitCustom" },
];

const miniSelectClass =
  "h-7 rounded-md border border-input bg-transparent px-1.5 text-xs outline-none focus-visible:border-ring focus-visible:ring-3 focus-visible:ring-ring/50";

export default function WorkoutPlanBuilderPage() {
  const t = useTranslations("admin");
  const queryClient = useQueryClient();
  const [name, setName] = useState("");
  const [split, setSplit] = useState<WorkoutSplit>("full_body");
  const [days, setDays] = useState<Record<string, WorkoutPlanExercise[]>>({});
  const [saving, setSaving] = useState(false);

  const plans = useQuery({ queryKey: ["coaching", "workout-plans"], queryFn: listWorkoutPlans });
  const exercises = useQuery({ queryKey: ["coaching", "exercises"], queryFn: () => listExercises() });
  const exerciseList = Array.isArray(exercises.data) ? exercises.data : exercises.data?.results ?? [];
  const planList = Array.isArray(plans.data) ? plans.data : plans.data?.results ?? [];

  function addExerciseToDay(day: string) {
    if (exerciseList.length === 0) return;
    setDays((prev) => ({
      ...prev,
      [day]: [
        ...(prev[day] ?? []),
        { exercise_id: exerciseList[0].id, sets: 3, reps: 10, rest_s: 60 },
      ],
    }));
  }

  function updateDayExercise(day: string, index: number, patch: Partial<WorkoutPlanExercise>) {
    setDays((prev) => ({
      ...prev,
      [day]: prev[day].map((e, i) => (i === index ? { ...e, ...patch } : e)),
    }));
  }

  async function save() {
    setSaving(true);
    try {
      const daysPayload: WorkoutPlanDay[] = Object.entries(days)
        .filter(([, exercises]) => exercises.length > 0)
        .map(([day, exercises]) => ({ day, exercises }));
      await createWorkoutPlan({ name, split, days: daysPayload });
      setName("");
      setDays({});
      queryClient.invalidateQueries({ queryKey: ["coaching", "workout-plans"] });
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="max-w-3xl space-y-6">
      <h1 className="flex items-center gap-2 text-xl font-semibold tracking-tight">
        <Dumbbell size={18} strokeWidth={2} className="text-primary" />
        {t("coachingWorkoutTitle")}
      </h1>

      <Card>
        <CardContent className="space-y-4">
          <div className="flex flex-wrap gap-3">
            <div className="space-y-1.5">
              <Label htmlFor="plan-name">{t("coachingWorkoutPlanName")}</Label>
              <Input
                id="plan-name"
                value={name}
                onChange={(e) => setName(e.target.value)}
                className="h-8 w-56"
              />
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="plan-split">{t("coachingWorkoutSplit")}</Label>
              <Select value={split} onValueChange={(v) => setSplit(v as WorkoutSplit)}>
                <SelectTrigger id="plan-split" className="h-8 w-40 text-sm">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {SPLITS.map((s) => (
                    <SelectItem key={s.value} value={s.value}>
                      {t(s.labelKey)}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
          </div>

          <div className="grid grid-cols-1 gap-3 md:grid-cols-2">
            {DAYS.map((day) => (
              <div key={day} className="space-y-2 rounded-lg border p-2.5">
                <div className="flex items-center justify-between">
                  <span className="text-sm font-medium uppercase">{t(DAY_KEYS[day])}</span>
                  <Button type="button" size="sm" variant="outline" onClick={() => addExerciseToDay(day)}>
                    {t("coachingWorkoutAddExercise")}
                  </Button>
                </div>
                {(days[day] ?? []).map((ex, i) => (
                  <div key={i} className="flex flex-wrap items-center gap-1 text-xs">
                    <select
                      value={ex.exercise_id}
                      onChange={(e) => updateDayExercise(day, i, { exercise_id: e.target.value })}
                      className={miniSelectClass}
                    >
                      {exerciseList.map((ex2) => (
                        <option key={ex2.id} value={ex2.id}>
                          {ex2.name_en}
                        </option>
                      ))}
                    </select>
                    <input
                      type="number"
                      value={ex.sets}
                      onChange={(e) => updateDayExercise(day, i, { sets: Number(e.target.value) })}
                      className={`${miniSelectClass} w-12`}
                      title={t("coachingWorkoutSetsTitle")}
                    />
                    <span className="text-muted-foreground">&times;</span>
                    <input
                      type="number"
                      value={ex.reps}
                      onChange={(e) => updateDayExercise(day, i, { reps: Number(e.target.value) })}
                      className={`${miniSelectClass} w-12`}
                      title={t("coachingWorkoutRepsTitle")}
                    />
                  </div>
                ))}
              </div>
            ))}
          </div>

          <Button onClick={save} disabled={saving || !name}>
            {saving ? "..." : t("coachingWorkoutSavePlan")}
          </Button>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle className="text-sm text-muted-foreground">{t("coachingWorkoutExistingPlans")}</CardTitle>
        </CardHeader>
        <CardContent>
          <ul className="divide-y text-sm">
            {planList.map((plan) => (
              <li key={plan.id} className="py-2">
                {plan.name} &middot; {plan.split.replace("_", " ")} &middot;{" "}
                {t("coachingWorkoutDaysCount", { count: plan.days.length })}
              </li>
            ))}
            {planList.length === 0 && (
              <li className="py-2 text-muted-foreground">{t("coachingWorkoutNoPlans")}</li>
            )}
          </ul>
        </CardContent>
      </Card>
    </div>
  );
}
