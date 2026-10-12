"use client";

import { useState } from "react";
import { useTranslations } from "next-intl";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import {
  getGymSettings,
  TEMPLATE_KEYS,
  updateGymSettings,
  type NotificationChannel,
} from "@fitkhata/api-client";
import { ArrowDown, ArrowUp, ListOrdered, ToggleLeft } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";

const CHANNEL_OPTIONS: NotificationChannel[] = ["push", "whatsapp", "sms", "email"];
const DEFAULT_ORDER: NotificationChannel[] = ["push", "whatsapp", "sms"];
const CHANNEL_LABEL_KEYS: Record<NotificationChannel, string> = {
  push: "notifChannelPush",
  whatsapp: "notifChannelWhatsapp",
  sms: "notifChannelSms",
  email: "notifChannelEmail",
};

export default function NotificationEventsPage() {
  const t = useTranslations("admin");
  const queryClient = useQueryClient();
  const gym = useQuery({ queryKey: ["gym-settings"], queryFn: getGymSettings });
  const [saving, setSaving] = useState(false);

  const events = gym.data?.settings.notification_events ?? {};
  const order = (gym.data?.settings.notification_channel_order ??
    DEFAULT_ORDER) as NotificationChannel[];

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

  if (gym.isLoading) {
    return (
      <div className="max-w-xl space-y-4">
        <Skeleton className="h-7 w-48" />
        <Skeleton className="h-40 w-full rounded-xl" />
      </div>
    );
  }

  return (
    <div className="max-w-xl space-y-5">
      <h1 className="text-xl font-semibold tracking-tight">{t("notifEventsTitle")}</h1>

      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <ListOrdered size={16} strokeWidth={2} className="text-primary" />
            {t("notifEventsChannelOrder")}
          </CardTitle>
          <p className="text-sm text-muted-foreground">{t("notifEventsChannelOrderBody")}</p>
        </CardHeader>
        <CardContent className="space-y-3">
          <ol className="divide-y">
            {order.map((channel, i) => (
              <li key={channel} className="flex items-center justify-between py-2 text-sm">
                <span>
                  {i + 1}. {t(CHANNEL_LABEL_KEYS[channel])}
                </span>
                <span className="flex gap-1">
                  <Button
                    variant="outline"
                    size="icon-sm"
                    disabled={i === 0 || saving}
                    onClick={() => moveChannel(i, -1)}
                    aria-label={t("notifEventsMoveUp")}
                  >
                    <ArrowUp size={13} strokeWidth={2} />
                  </Button>
                  <Button
                    variant="outline"
                    size="icon-sm"
                    disabled={i === order.length - 1 || saving}
                    onClick={() => moveChannel(i, 1)}
                    aria-label={t("notifEventsMoveDown")}
                  >
                    <ArrowDown size={13} strokeWidth={2} />
                  </Button>
                </span>
              </li>
            ))}
          </ol>
          <p className="text-xs text-muted-foreground">
            {t("notifEventsChannelsNotShown", {
              channels:
                CHANNEL_OPTIONS.filter((c) => !order.includes(c))
                  .map((c) => t(CHANNEL_LABEL_KEYS[c]))
                  .join(", ") || t("notifEventsNoneLabel"),
            })}
          </p>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <ToggleLeft size={16} strokeWidth={2} className="text-primary" />
            {t("notifEventsEventsHeading")}
          </CardTitle>
        </CardHeader>
        <CardContent>
          <ul className="divide-y">
            {TEMPLATE_KEYS.map((eventKey) => {
              const enabled = events[eventKey] ?? true;
              return (
                <li key={eventKey} className="flex items-center justify-between py-2 text-sm">
                  <span>{eventKey}</span>
                  <Button
                    variant={enabled ? "default" : "outline"}
                    size="sm"
                    disabled={saving}
                    onClick={() => toggleEvent(eventKey)}
                  >
                    {enabled ? t("notifEventsOn") : t("notifEventsOff")}
                  </Button>
                </li>
              );
            })}
          </ul>
        </CardContent>
      </Card>
    </div>
  );
}
