"use client";

import { useParams } from "next/navigation";
import { useQuery } from "@tanstack/react-query";
import {
  getClientProgress,
  listClientProfiles,
  listMeasurements,
  listWorkoutLogs,
  type BodyMeasurement,
} from "@fitkhata/api-client";
import { Dumbbell, LineChart, TriangleAlert } from "lucide-react";

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";

function ProgressBar({ label, pct }: { label: string; pct: number }) {
  return (
    <div className="space-y-1">
      <div className="flex justify-between text-sm">
        <span>{label}</span>
        <span className="font-dashboard-mono text-muted-foreground">{pct.toFixed(0)}%</span>
      </div>
      <div className="h-2 w-full rounded-full bg-muted">
        <div
          className="h-2 rounded-full bg-primary transition-[width]"
          style={{ width: `${Math.max(0, Math.min(100, pct))}%` }}
        />
      </div>
    </div>
  );
}

function WeightTrendChart({ measurements }: { measurements: BodyMeasurement[] }) {
  const points = [...measurements].reverse(); // oldest -> newest, left to right
  if (points.length < 2) {
    return (
      <p className="text-sm text-muted-foreground">Not enough measurements yet for a trend chart.</p>
    );
  }
  const weights = points.map((m) => Number(m.weight_kg));
  const min = Math.min(...weights);
  const max = Math.max(...weights);
  const range = max - min || 1;
  const width = 280;
  const height = 80;
  const coords = points.map((m, i) => {
    const x = (i / (points.length - 1)) * width;
    const y = height - ((Number(m.weight_kg) - min) / range) * height;
    return `${x},${y}`;
  });

  return (
    <svg viewBox={`0 0 ${width} ${height}`} className="h-20 w-full text-primary">
      <polyline points={coords.join(" ")} fill="none" stroke="currentColor" strokeWidth={2} />
    </svg>
  );
}

export default function ClientCoachingProfilePage() {
  const { memberId } = useParams<{ memberId: string }>();

  const profiles = useQuery({ queryKey: ["coaching", "client-profiles"], queryFn: listClientProfiles });
  const profileList = Array.isArray(profiles.data) ? profiles.data : profiles.data?.results ?? [];
  const profile = profileList.find((p) => p.member === memberId);

  const progress = useQuery({
    queryKey: ["coaching", "progress", profile?.id],
    queryFn: () => getClientProgress(profile!.id),
    enabled: Boolean(profile),
  });

  const measurements = useQuery({
    queryKey: ["coaching", "measurements", memberId],
    queryFn: () => listMeasurements(memberId),
  });
  const measurementList = Array.isArray(measurements.data)
    ? measurements.data
    : measurements.data?.results ?? [];

  const logs = useQuery({
    queryKey: ["coaching", "workout-logs", memberId],
    queryFn: () => listWorkoutLogs(memberId),
  });
  const logList = Array.isArray(logs.data) ? logs.data : logs.data?.results ?? [];

  if (profiles.isLoading) {
    return (
      <div className="max-w-2xl space-y-6">
        <Skeleton className="h-8 w-48" />
        <Skeleton className="h-32 w-full rounded-xl" />
      </div>
    );
  }
  if (!profile) {
    return (
      <p className="flex items-center gap-1.5 text-sm text-destructive">
        <TriangleAlert size={14} strokeWidth={2} />
        This member has no coaching profile yet.
      </p>
    );
  }

  return (
    <div className="max-w-2xl space-y-6">
      <div>
        <h1 className="text-xl font-semibold tracking-tight">{profile.member_name}</h1>
        <p className="font-dashboard-mono mt-0.5 text-sm text-muted-foreground">
          Goal: {profile.primary_goal.replace("_", " ")} &middot; {profile.starting_weight_kg}kg &rarr;{" "}
          {profile.target_weight_kg}kg
        </p>
      </div>

      {progress.data && (
        <Card>
          <CardContent className="space-y-3">
            <ProgressBar label="Goal progress" pct={progress.data.goal_progress_pct} />
            <ProgressBar label="Attendance (last 4 weeks)" pct={progress.data.attendance_pct} />
          </CardContent>
        </Card>
      )}

      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2 text-sm text-muted-foreground">
            <LineChart size={15} strokeWidth={2} />
            Weight trend
          </CardTitle>
        </CardHeader>
        <CardContent>
          <WeightTrendChart measurements={measurementList} />
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2 text-sm text-muted-foreground">
            <Dumbbell size={15} strokeWidth={2} />
            Recent workout logs
          </CardTitle>
        </CardHeader>
        <CardContent>
          <ul className="divide-y text-sm">
            {logList.slice(0, 10).map((log) => (
              <li key={log.id} className="flex items-center justify-between py-2">
                <span>
                  {log.logged_on} &middot; {log.exercise_name_en}
                </span>
                <span className="font-dashboard-mono text-muted-foreground">
                  {log.sets.length} set(s)
                </span>
              </li>
            ))}
            {logList.length === 0 && (
              <li className="py-2 text-muted-foreground">No workout logs yet.</li>
            )}
          </ul>
        </CardContent>
      </Card>

      {profile.coach_notes && (
        <section className="space-y-1">
          <h2 className="text-sm font-medium text-muted-foreground">Coach notes</h2>
          <p className="text-sm text-foreground/80">{profile.coach_notes}</p>
        </section>
      )}
    </div>
  );
}
