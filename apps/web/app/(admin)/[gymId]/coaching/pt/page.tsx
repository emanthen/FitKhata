"use client";

import { useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import {
  createPTPack,
  createPTSession,
  listPTPacks,
  listPTSessions,
  markPTSessionAttended,
} from "@fitkhata/api-client";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";

export default function PTPage() {
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
      <h1 className="text-2xl font-semibold">Personal training</h1>

      <form onSubmit={sellPack} className="flex flex-wrap items-end gap-3 rounded border p-3">
        <div className="space-y-1">
          <Label htmlFor="pt-member">Member ID</Label>
          <Input id="pt-member" value={memberId} onChange={(e) => setMemberId(e.target.value)} className="w-40" required />
        </div>
        <div className="space-y-1">
          <Label htmlFor="pt-sessions">Sessions</Label>
          <Input
            id="pt-sessions"
            type="number"
            value={sessionsTotal}
            onChange={(e) => setSessionsTotal(e.target.value)}
            className="w-20"
          />
        </div>
        <div className="space-y-1">
          <Label htmlFor="pt-price">Price (NPR)</Label>
          <Input id="pt-price" value={priceNpr} onChange={(e) => setPriceNpr(e.target.value)} className="w-28" />
        </div>
        <div className="space-y-1">
          <Label htmlFor="pt-expires">Expires on</Label>
          <Input
            id="pt-expires"
            type="date"
            value={expiresOn}
            onChange={(e) => setExpiresOn(e.target.value)}
            required
          />
        </div>
        <Button type="submit">Sell pack</Button>
      </form>

      <div className="grid grid-cols-1 gap-3 md:grid-cols-2">
        <ul className="space-y-2">
          {packList.map((pack) => (
            <li
              key={pack.id}
              className={`cursor-pointer rounded border px-3 py-2 text-sm ${selectedPack === pack.id ? "border-primary" : ""}`}
              onClick={() => setSelectedPack(pack.id)}
            >
              {pack.sessions_used}/{pack.sessions_total} sessions used &middot; expires {pack.expires_on}
            </li>
          ))}
          {packList.length === 0 && <li className="text-sm opacity-60">No PT packs sold yet.</li>}
        </ul>

        {selectedPack && (
          <div className="space-y-3 rounded border p-3">
            <h2 className="text-sm font-medium">Sessions</h2>
            <div className="flex gap-2">
              <Input
                type="datetime-local"
                value={scheduledAt}
                onChange={(e) => setScheduledAt(e.target.value)}
                className="h-8"
              />
              <Button size="sm" onClick={scheduleSession}>
                Schedule
              </Button>
            </div>
            <ul className="space-y-1 text-sm">
              {sessionsForPack.map((session) => (
                <li key={session.id} className="flex items-center justify-between rounded border px-2 py-1">
                  <span>{new Date(session.scheduled_at).toLocaleString()}</span>
                  <Button
                    size="sm"
                    variant={session.attended ? "secondary" : "outline"}
                    onClick={async () => {
                      await markPTSessionAttended(session.id, !session.attended);
                      refresh();
                    }}
                  >
                    {session.attended ? "Attended" : "Mark attended"}
                  </Button>
                </li>
              ))}
              {sessionsForPack.length === 0 && (
                <li className="text-sm opacity-60">No sessions scheduled.</li>
              )}
            </ul>
          </div>
        )}
      </div>
    </div>
  );
}
