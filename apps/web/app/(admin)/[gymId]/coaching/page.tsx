"use client";

import { useParams } from "next/navigation";
import Link from "next/link";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { approveCoachingReport, getTrainerDashboard, rejectCoachingReport } from "@fitkhata/api-client";

import { Button } from "@/components/ui/button";

export default function CoachingDashboardPage() {
  const { gymId } = useParams<{ gymId: string }>();
  const queryClient = useQueryClient();
  const query = useQuery({ queryKey: ["coaching", "trainer-dashboard"], queryFn: getTrainerDashboard });

  function refresh() {
    queryClient.invalidateQueries({ queryKey: ["coaching", "trainer-dashboard"] });
  }

  return (
    <div className="max-w-2xl space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-semibold">Coaching</h1>
        <div className="flex gap-3 text-sm">
          <Link href={`/${gymId}/coaching/plans/workout`} className="text-blue-600 hover:underline">
            Workout plans
          </Link>
          <Link href={`/${gymId}/coaching/plans/diet`} className="text-blue-600 hover:underline">
            Diet plans
          </Link>
          <Link href={`/${gymId}/coaching/classes`} className="text-blue-600 hover:underline">
            Classes
          </Link>
          <Link href={`/${gymId}/coaching/pt`} className="text-blue-600 hover:underline">
            PT
          </Link>
        </div>
      </div>

      {query.isLoading && <p className="text-sm opacity-60">Loading...</p>}

      {query.data && (
        <>
          <section className="space-y-2">
            <h2 className="text-lg font-medium">My clients</h2>
            <ul className="space-y-2">
              {query.data.clients.map((client) => (
                <li key={client.id} className="rounded border px-3 py-2 text-sm">
                  <Link href={`/${gymId}/coaching/clients/${client.member}`} className="font-medium hover:underline">
                    {client.member_name}
                  </Link>
                  <span className="ml-2 opacity-60">{client.primary_goal.replace("_", " ")}</span>
                </li>
              ))}
              {query.data.clients.length === 0 && (
                <li className="text-sm opacity-60">No clients assigned yet.</li>
              )}
            </ul>
          </section>

          <section className="space-y-2">
            <h2 className="text-lg font-medium">Pending approvals</h2>
            <p className="text-sm opacity-60">
              AI-drafted suggestions wait here until you approve or reject them — a member never
              sees anything before that.
            </p>
            <ul className="space-y-2">
              {query.data.pending_approvals.map((report) => (
                <li key={report.id} className="space-y-2 rounded border p-3 text-sm">
                  <div className="flex items-center justify-between">
                    <span className="font-medium">
                      {report.member_name} &middot; week of {report.week_start}
                    </span>
                    {Array.isArray(report.flags) && report.flags.length > 0 && (
                      <span className="text-xs text-amber-600">
                        {(report.flags as string[]).join(", ")}
                      </span>
                    )}
                  </div>
                  <ul className="space-y-1 opacity-80">
                    {report.suggestions.map((s, i) => (
                      <li key={i}>
                        <span className="font-medium capitalize">{s.type}:</span> {s.text_en}
                      </li>
                    ))}
                  </ul>
                  <div className="flex gap-2">
                    <Button
                      size="sm"
                      onClick={async () => {
                        await approveCoachingReport(report.id);
                        refresh();
                      }}
                    >
                      Approve
                    </Button>
                    <Button
                      size="sm"
                      variant="outline"
                      onClick={async () => {
                        await rejectCoachingReport(report.id);
                        refresh();
                      }}
                    >
                      Reject
                    </Button>
                  </div>
                </li>
              ))}
              {query.data.pending_approvals.length === 0 && (
                <li className="text-sm opacity-60">Nothing waiting on review.</li>
              )}
            </ul>
          </section>
        </>
      )}
    </div>
  );
}
