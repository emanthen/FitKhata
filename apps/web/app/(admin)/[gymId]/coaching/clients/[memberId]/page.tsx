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

function ProgressBar({ label, pct }: { label: string; pct: number }) {
  return (
    <div className="space-y-1">
      <div className="flex justify-between text-sm">
        <span>{label}</span>
        <span className="opacity-60">{pct.toFixed(0)}%</span>
      </div>
      <div className="h-2 w-full rounded bg-muted">
        <div
          className="h-2 rounded bg-primary transition-[width]"
          style={{ width: `${Math.max(0, Math.min(100, pct))}%` }}
        />
      </div>
    </div>
  );
}

function WeightTrendChart({ measurements }: { measurements: BodyMeasurement[] }) {
  const points = [...measurements].reverse(); // oldest -> newest, left to right
  if (points.length < 2) {
    return <p className="text-sm opacity-60">Not enough measurements yet for a trend chart.</p>;
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

  if (profiles.isLoading) return <p className="text-sm opacity-60">Loading...</p>;
  if (!profile) return <p className="text-sm text-red-600">This member has no coaching profile yet.</p>;

  return (
    <div className="max-w-2xl space-y-6">
      <div>
        <h1 className="text-2xl font-semibold">{profile.member_name}</h1>
        <p className="text-sm opacity-60">
          Goal: {profile.primary_goal.replace("_", " ")} &middot; {profile.starting_weight_kg}kg &rarr;{" "}
          {profile.target_weight_kg}kg
        </p>
      </div>

      {progress.data && (
        <section className="space-y-3 rounded border p-4">
          <ProgressBar label="Goal progress" pct={progress.data.goal_progress_pct} />
          <ProgressBar label="Attendance (last 4 weeks)" pct={progress.data.attendance_pct} />
        </section>
      )}

      <section className="space-y-2 rounded border p-4">
        <h2 className="text-lg font-medium">Weight trend</h2>
        <WeightTrendChart measurements={measurementList} />
      </section>

      <section className="space-y-2">
        <h2 className="text-lg font-medium">Recent workout logs</h2>
        <ul className="space-y-1 text-sm">
          {logList.slice(0, 10).map((log) => (
            <li key={log.id} className="flex justify-between rounded border px-3 py-2">
              <span>
                {log.logged_on} &middot; {log.exercise_name_en}
              </span>
              <span className="opacity-60">{log.sets.length} set(s)</span>
            </li>
          ))}
          {logList.length === 0 && <li className="text-sm opacity-60">No workout logs yet.</li>}
        </ul>
      </section>

      {profile.coach_notes && (
        <section className="space-y-1">
          <h2 className="text-lg font-medium">Coach notes</h2>
          <p className="text-sm opacity-80">{profile.coach_notes}</p>
        </section>
      )}
    </div>
  );
}
