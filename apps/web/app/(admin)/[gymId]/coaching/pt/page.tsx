"use client";

import { useState } from "react";
import { useTranslations } from "next-intl";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import {
  createPTPack,
  createPTSession,
  listPTPacks,
  listPTSessions,
  markPTSessionAttended,
} from "@fitkhata/api-client";
import { CircleCheck, Dumbbell } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";

export default function PTPage() {
  const t = useTranslations("admin");
  const queryClient = useQueryClient();
  const [memberId, setMemberId] = useState("");
  const [sessionsTotal, setSessionsTotal] = useState("10");
  const [priceNpr, setPriceNpr] = useState("10000");
  const [expiresOn, setExpiresOn] = useState("");
  const [selectedPack, setSelectedPack] = useState<string | null>(null);
  const [scheduledAt, setScheduledAt] = useState("");

  const packs = useQuery({ queryKey: ["coaching", "pt-packs"], queryFn: listPTPacks });
  const packList = Array.isArray(packs.data) ? packs.data : packs.data?.results ?? [];

  const sessions = useQuery({ queryKey: ["coaching", "pt-sessions"], queryFn: listPTSessions });
  const sessionList = Array.isArray(sessions.data) ? sessions.data : sessions.data?.results ?? [];
  const sessionsForPack = sessionList.filter((s) => s.pack === selectedPack);

  function refresh() {
    queryClient.invalidateQueries({ queryKey: ["coaching", "pt-packs"] });
    queryClient.invalidateQueries({ queryKey: ["coaching", "pt-sessions"] });
  }

  async function sellPack(e: React.FormEvent) {
    e.preventDefault();
    await createPTPack({
      member: memberId,
      sessions_total: Number(sessionsTotal),
      price_npr: priceNpr,
      expires_on: expiresOn,
    });
    setMemberId("");
    refresh();
  }

  async function scheduleSession() {
    if (!selectedPack || !scheduledAt) return;
    await createPTSession({ pack: selectedPack, scheduled_at: scheduledAt });
    setScheduledAt("");
    refresh();
  }

  return (
    <div className="max-w-3xl space-y-6">
      <h1 className="flex items-center gap-2 text-xl font-semibold tracking-tight">
        <Dumbbell size={18} strokeWidth={2} className="text-primary" />
        {t("coachingPtTitle")}
      </h1>

      <Card>
        <CardContent>
          <form onSubmit={sellPack} className="flex flex-wrap items-end gap-3">
            <div className="space-y-1.5">
              <Label htmlFor="pt-member">{t("coachingPtMemberId")}</Label>
              <Input
                id="pt-member"
                value={memberId}
                onChange={(e) => setMemberId(e.target.value)}
                className="h-8 w-40"
                required
              />
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="pt-sessions">{t("coachingPtSessionsLabel")}</Label>
              <Input
                id="pt-sessions"
                type="number"
                value={sessionsTotal}
                onChange={(e) => setSessionsTotal(e.target.value)}
                className="h-8 w-20"
              />
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="pt-price">{t("coachingPtPriceNpr")}</Label>
              <Input
                id="pt-price"
                value={priceNpr}
                onChange={(e) => setPriceNpr(e.target.value)}
                className="h-8 w-28"
              />
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="pt-expires">{t("coachingPtExpiresOn")}</Label>
              <Input
                id="pt-expires"
                type="date"
                value={expiresOn}
                onChange={(e) => setExpiresOn(e.target.value)}
                className="h-8"
                required
              />
            </div>
            <Button type="submit" size="sm">
              {t("coachingPtSellPack")}
            </Button>
          </form>
        </CardContent>
      </Card>

      <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
        <ul className="space-y-2">
          {packList.map((pack) => (
            <li
              key={pack.id}
              className={`font-dashboard-mono cursor-pointer rounded-xl border p-3 text-sm transition-colors hover:bg-muted/50 ${
                selectedPack === pack.id ? "border-primary bg-primary/5" : ""
              }`}
              onClick={() => setSelectedPack(pack.id)}
            >
              {t("coachingPtSessionsUsedLine", {
                used: pack.sessions_used,
                total: pack.sessions_total,
                date: pack.expires_on,
              })}
            </li>
          ))}
          {packList.length === 0 && (
            <li className="text-sm text-muted-foreground">{t("coachingPtNoPacks")}</li>
          )}
        </ul>

        {selectedPack && (
          <Card>
            <CardHeader>
              <CardTitle className="text-sm text-muted-foreground">{t("coachingPtSessionsLabel")}</CardTitle>
            </CardHeader>
            <CardContent className="space-y-3">
              <div className="flex gap-2">
                <Input
                  type="datetime-local"
                  value={scheduledAt}
                  onChange={(e) => setScheduledAt(e.target.value)}
                  className="h-8"
                />
                <Button size="sm" onClick={scheduleSession}>
                  {t("coachingPtSchedule")}
                </Button>
              </div>
              <ul className="divide-y text-sm">
                {sessionsForPack.map((session) => (
                  <li key={session.id} className="flex items-center justify-between py-1.5">
                    <span className="font-dashboard-mono">
                      {new Date(session.scheduled_at).toLocaleString()}
                    </span>
                    <Button
                      size="sm"
                      variant={session.attended ? "secondary" : "outline"}
                      onClick={async () => {
                        await markPTSessionAttended(session.id, !session.attended);
                        refresh();
                      }}
                    >
                      {session.attended && (
                        <CircleCheck size={13} strokeWidth={2} data-icon="inline-start" />
                      )}
                      {session.attended ? t("coachingPtAttended") : t("coachingPtMarkAttended")}
                    </Button>
                  </li>
                ))}
                {sessionsForPack.length === 0 && (
                  <li className="py-1.5 text-muted-foreground">{t("coachingPtNoSessions")}</li>
                )}
              </ul>
            </CardContent>
          </Card>
        )}
      </div>
    </div>
  );
}
