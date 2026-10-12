"use client";

import { useParams } from "next/navigation";
import Link from "next/link";
import { useTranslations } from "next-intl";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { approveCoachingReport, getTrainerDashboard, rejectCoachingReport } from "@fitkhata/api-client";
import { Apple, CalendarDays, Dumbbell, HeartPulse, TriangleAlert, Users } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";

export default function CoachingDashboardPage() {
  const { gymId } = useParams<{ gymId: string }>();
  const t = useTranslations("admin");
  const queryClient = useQueryClient();
  const query = useQuery({ queryKey: ["coaching", "trainer-dashboard"], queryFn: getTrainerDashboard });

  function refresh() {
    queryClient.invalidateQueries({ queryKey: ["coaching", "trainer-dashboard"] });
  }

  return (
    <div className="max-w-2xl space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="flex items-center gap-2 text-xl font-semibold tracking-tight">
          <HeartPulse size={18} strokeWidth={2} className="text-primary" />
          {t("coachingTitle")}
        </h1>
        <div className="flex gap-2">
          <Button variant="outline" size="sm" asChild>
            <Link href={`/${gymId}/coaching/plans/workout`}>
              <Dumbbell size={13} strokeWidth={2} data-icon="inline-start" />
              {t("coachingNavWorkout")}
            </Link>
          </Button>
          <Button variant="outline" size="sm" asChild>
            <Link href={`/${gymId}/coaching/plans/diet`}>
              <Apple size={13} strokeWidth={2} data-icon="inline-start" />
              {t("coachingNavDiet")}
            </Link>
          </Button>
          <Button variant="outline" size="sm" asChild>
            <Link href={`/${gymId}/coaching/classes`}>
              <CalendarDays size={13} strokeWidth={2} data-icon="inline-start" />
              {t("coachingNavClasses")}
            </Link>
          </Button>
          <Button variant="outline" size="sm" asChild>
            <Link href={`/${gymId}/coaching/pt`}>{t("coachingNavPt")}</Link>
          </Button>
        </div>
      </div>

      {query.isLoading && <Skeleton className="h-60 w-full rounded-xl" />}

      {query.data && (
        <>
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <Users size={16} strokeWidth={2} className="text-primary" />
                {t("coachingMyClients")}
              </CardTitle>
            </CardHeader>
            <CardContent>
              <ul className="divide-y">
                {query.data.clients.map((client) => (
                  <li key={client.id} className="py-2 text-sm">
                    <Link
                      href={`/${gymId}/coaching/clients/${client.member}`}
                      className="font-medium hover:underline"
                    >
                      {client.member_name}
                    </Link>
                    <span className="ml-2 text-muted-foreground">
                      {client.primary_goal.replace("_", " ")}
                    </span>
                  </li>
                ))}
                {query.data.clients.length === 0 && (
                  <li className="py-2 text-sm text-muted-foreground">{t("coachingNoClients")}</li>
                )}
              </ul>
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle>{t("coachingPendingApprovals")}</CardTitle>
              <p className="text-sm text-muted-foreground">{t("coachingPendingApprovalsBody")}</p>
            </CardHeader>
            <CardContent>
              <ul className="space-y-3">
                {query.data.pending_approvals.map((report) => (
                  <li key={report.id} className="space-y-2 rounded-lg border p-3 text-sm">
                    <div className="flex items-center justify-between">
                      <span className="font-medium">
                        {report.member_name} &middot; {t("coachingWeekOf", { date: report.week_start })}
                      </span>
                      {Array.isArray(report.flags) && report.flags.length > 0 && (
                        <span className="flex items-center gap-1 text-xs text-accent">
                          <TriangleAlert size={12} strokeWidth={2} />
                          {(report.flags as string[]).join(", ")}
                        </span>
                      )}
                    </div>
                    <ul className="space-y-1 text-foreground/80">
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
                        {t("coachingApprove")}
                      </Button>
                      <Button
                        size="sm"
                        variant="outline"
                        onClick={async () => {
                          await rejectCoachingReport(report.id);
                          refresh();
                        }}
                      >
                        {t("coachingReject")}
                      </Button>
                    </div>
                  </li>
                ))}
                {query.data.pending_approvals.length === 0 && (
                  <li className="text-sm text-muted-foreground">{t("coachingNothingWaiting")}</li>
                )}
              </ul>
            </CardContent>
          </Card>
        </>
      )}
    </div>
  );
}
