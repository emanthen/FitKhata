"use client";

import { useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import {
  getGymSettings,
  TEMPLATE_KEYS,
  updateGymSettings,
  type NotificationChannel,
} from "@fitkhata/api-client";

import { Button } from "@/components/ui/button";

const CHANNEL_OPTIONS: NotificationChannel[] = ["push", "whatsapp", "sms", "email"];
const DEFAULT_ORDER: NotificationChannel[] = ["push", "whatsapp", "sms"];

export default function NotificationEventsPage() {
  const queryClient = useQueryClient();
  const gym = useQuery({ queryKey: ["gym-settings"], queryFn: getGymSettings });
  const [saving, setSaving] = useState(false);

  const events = gym.data?.settings.notification_events ?? {};
  const order = gym.data?.settings.notification_channel_order ?? DEFAULT_ORDER;

  async function toggleEvent(eventKey: string) {
    if (!gym.data) return;
    setSaving(true);
    try {
      const nextEvents = { ...events, [eventKey]: !(events[eventKey] ?? true) };
      await updateGymSettings({
        settings: { ...gym.data.settings, notification_events: nextEvents },
      });
      queryClient.invalidateQueries({ queryKey: ["gym-settings"] });
    } finally {
      setSaving(false);
    }
  }

  function moveChannel(index: number, direction: -1 | 1) {
    const next = [...order];
    const swapWith = index + direction;
    if (swapWith < 0 || swapWith >= next.length || !gym.data) return;
    [next[index], next[swapWith]] = [next[swapWith], next[index]];
    setSaving(true);
    updateGymSettings({
      settings: { ...gym.data.settings, notification_channel_order: next },
    })
      .then(() => queryClient.invalidateQueries({ queryKey: ["gym-settings"] }))
      .finally(() => setSaving(false));
  }

  if (gym.isLoading) return <p className="text-sm opacity-60">Loading...</p>;

  return (
    <div className="max-w-xl space-y-8">
      <h1 className="text-2xl font-semibold">Notification triggers</h1>

      <section className="space-y-2">
        <h2 className="text-lg font-medium">Channel order</h2>
        <p className="text-sm opacity-60">
          notify() tries each channel in this order, falling back to the next if a member has
          no usable destination on the current one.
        </p>
        <ol className="space-y-1">
          {order.map((channel, i) => (
            <li key={channel} className="flex items-center justify-between rounded border px-3 py-2">
              <span className="capitalize">
                {i + 1}. {channel}
              </span>
              <span className="flex gap-1">
                <Button
                  variant="outline"
                  size="sm"
                  disabled={i === 0 || saving}
                  onClick={() => moveChannel(i, -1)}
                >
                  ↑
                </Button>
                <Button
                  variant="outline"
                  size="sm"
                  disabled={i === order.length - 1 || saving}
                  onClick={() => moveChannel(i, 1)}
                >
                  ↓
                </Button>
              </span>
            </li>
          ))}
        </ol>
        <p className="text-xs opacity-50">
          Channels not shown here ({CHANNEL_OPTIONS.filter((c) => !order.includes(c)).join(", ") || "none"}) are never tried automatically.
        </p>
      </section>

      <section className="space-y-2">
        <h2 className="text-lg font-medium">Events</h2>
        <ul className="space-y-1">
          {TEMPLATE_KEYS.map((eventKey) => {
            const enabled = events[eventKey] ?? true;
            return (
              <li
                key={eventKey}
                className="flex items-center justify-between rounded border px-3 py-2 text-sm"
              >
                <span>{eventKey}</span>
                <Button
                  variant={enabled ? "default" : "outline"}
                  size="sm"
                  disabled={saving}
                  onClick={() => toggleEvent(eventKey)}
                >
                  {enabled ? "On" : "Off"}
                </Button>
              </li>
            );
          })}
        </ul>
      </section>
    </div>
  );
}
