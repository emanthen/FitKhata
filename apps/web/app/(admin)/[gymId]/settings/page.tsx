"use client";

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import Link from "next/link";
import { listSessions, revokeSession, type DeviceSession } from "@fitkhata/api-client";
import { Bell, ChevronRight, CreditCard, Laptop, Ticket } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

function SettingsLink({ href, label }: { href: string; label: string }) {
  return (
    <Link
      href={href}
      className="flex items-center justify-between rounded-lg px-2.5 py-2 text-sm text-foreground/80 transition-colors hover:bg-muted hover:text-foreground"
    >
      {label}
      <ChevronRight size={15} strokeWidth={2} className="text-muted-foreground" />
    </Link>
  );
}

export default function SettingsPage() {
  const { gymId } = useParams<{ gymId: string }>();
  const [sessions, setSessions] = useState<DeviceSession[] | null>(null);

  function load() {
    listSessions().then(setSessions);
  }

  useEffect(() => {
    load();
  }, []);

  async function revoke(id: string) {
    await revokeSession(id);
    load();
  }

  return (
    <div className="max-w-2xl space-y-4">
      <h1 className="text-xl font-semibold tracking-tight">Settings</h1>

      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Ticket size={16} strokeWidth={2} className="text-primary" />
            Membership
          </CardTitle>
        </CardHeader>
        <CardContent className="flex flex-col">
          <SettingsLink href={`/${gymId}/settings/plans`} label="Plans & add-ons" />
          <SettingsLink href={`/${gymId}/settings/promo-codes`} label="Promo codes" />
          <SettingsLink href={`/${gymId}/members/import`} label="Import members" />
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <CreditCard size={16} strokeWidth={2} className="text-primary" />
            Billing
          </CardTitle>
        </CardHeader>
        <CardContent className="flex flex-col">
          <SettingsLink href={`/${gymId}/settings/payments`} label="Payment gateways & VAT" />
          <SettingsLink href={`/${gymId}/billing/shift`} label="Cash shift" />
          <SettingsLink href={`/${gymId}/billing/settlement`} label="Settlement report" />
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Bell size={16} strokeWidth={2} className="text-primary" />
            Notifications
          </CardTitle>
        </CardHeader>
        <CardContent className="flex flex-col">
          <SettingsLink href={`/${gymId}/settings/notifications/templates`} label="Templates" />
          <SettingsLink href={`/${gymId}/settings/notifications/events`} label="Event triggers" />
          <SettingsLink href={`/${gymId}/notifications/broadcast`} label="Broadcast" />
          <SettingsLink href={`/${gymId}/notifications/log`} label="Delivery log" />
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Laptop size={16} strokeWidth={2} className="text-primary" />
            Device sessions
          </CardTitle>
        </CardHeader>
        <CardContent>
          <ul className="divide-y">
            {sessions?.map((session) => (
              <li key={session.id} className="flex items-center justify-between py-2.5 text-sm">
                <span>
                  {session.user_agent || "Unknown device"} &middot; {session.ip ?? "unknown IP"}
                  <br />
                  <span className="text-xs text-muted-foreground">
                    Last used {new Date(session.last_used_at).toLocaleString()}
                  </span>
                </span>
                <Button
                  variant="ghost"
                  size="sm"
                  className="text-destructive hover:text-destructive"
                  onClick={() => revoke(session.id)}
                >
                  Revoke
                </Button>
              </li>
            ))}
            {sessions?.length === 0 && (
              <li className="py-2.5 text-sm text-muted-foreground">No active sessions.</li>
            )}
          </ul>
        </CardContent>
      </Card>
    </div>
  );
}
