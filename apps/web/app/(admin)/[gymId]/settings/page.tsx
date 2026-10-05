"use client";

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import Link from "next/link";
import { listSessions, revokeSession, type DeviceSession } from "@fitkhata/api-client";

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
    <div className="space-y-4">
      <h1 className="text-2xl font-semibold">Settings</h1>

      <section className="space-y-2">
        <h2 className="text-lg font-medium">Membership</h2>
        <div className="flex gap-4 text-sm">
          <Link href={`/${gymId}/settings/plans`} className="text-blue-600 hover:underline">
            Plans &amp; add-ons
          </Link>
          <Link href={`/${gymId}/settings/promo-codes`} className="text-blue-600 hover:underline">
            Promo codes
          </Link>
          <Link href={`/${gymId}/members/import`} className="text-blue-600 hover:underline">
            Import members
          </Link>
        </div>
      </section>

      <section className="space-y-2">
        <h2 className="text-lg font-medium">Device sessions</h2>
        <ul className="space-y-2">
          {sessions?.map((session) => (
            <li
              key={session.id}
              className="flex items-center justify-between rounded border px-3 py-2 text-sm"
            >
              <span>
                {session.user_agent || "Unknown device"} · {session.ip ?? "unknown IP"}
                <br />
                <span className="opacity-60">
                  Last used {new Date(session.last_used_at).toLocaleString()}
                </span>
              </span>
              <button onClick={() => revoke(session.id)} className="text-red-600 hover:underline">
                Revoke
              </button>
            </li>
          ))}
        </ul>
      </section>
    </div>
  );
}
