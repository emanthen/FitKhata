"use client";

import { useState } from "react";
import { useTranslations } from "next-intl";
import { useQuery } from "@tanstack/react-query";
import {
  getMonthlyNotificationCost,
  listNotificationLog,
  type Notification as NotificationLogEntry,
  type NotificationChannel,
  type Page,
} from "@fitkhata/api-client";
import { BellRing } from "lucide-react";

import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { Badge } from "@/components/ui/badge";
import { formatNpr } from "@/lib/money";

const STATUS_FILTERS = ["all", "queued", "sent", "delivered", "failed"] as const;
const STATUS_LABEL_KEYS: Record<(typeof STATUS_FILTERS)[number], string> = {
  all: "notifStatusAll",
  queued: "notifStatusQueued",
  sent: "notifStatusSent",
  delivered: "notifStatusDelivered",
  failed: "notifStatusFailed",
};
const CHANNEL_FILTERS: ("all" | NotificationChannel)[] = ["all", "sms", "whatsapp", "push", "email"];
const CHANNEL_LABEL_KEYS: Record<"all" | NotificationChannel, string> = {
  all: "notifChannelAll",
  sms: "notifChannelSms",
  whatsapp: "notifChannelWhatsapp",
  push: "notifChannelPush",
  email: "notifChannelEmail",
};

function unwrap(data: NotificationLogEntry[] | Page<NotificationLogEntry> | undefined): NotificationLogEntry[] {
  if (!data) return [];
  return Array.isArray(data) ? data : data.results;
}

export default function NotificationLogPage() {
  const t = useTranslations("admin");
  const [status, setStatus] = useState<(typeof STATUS_FILTERS)[number]>("all");
  const [channel, setChannel] = useState<"all" | NotificationChannel>("all");

  const log = useQuery({
    queryKey: ["notification-log", status, channel],
    queryFn: () =>
      listNotificationLog({
        status: status === "all" ? undefined : status,
        channel: channel === "all" ? undefined : channel,
      }),
  });
  const monthlyCost = useQuery({
    queryKey: ["notification-log", "monthly-cost"],
    queryFn: getMonthlyNotificationCost,
  });

  const rows = unwrap(log.data);

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h1 className="flex items-center gap-2 text-xl font-semibold tracking-tight">
          <BellRing size={18} strokeWidth={2} className="text-primary" />
          {t("settingsDeliveryLog")}
        </h1>
        {monthlyCost.data && (
          <p className="font-dashboard-mono text-sm text-muted-foreground">
            {t("notifLogThisMonth", { cost: formatNpr(monthlyCost.data.cost_npr, { symbol: true }) })}
          </p>
        )}
      </div>

      <div className="flex gap-2">
        <Select value={status} onValueChange={(v) => setStatus(v as typeof status)}>
          <SelectTrigger className="h-8 w-40 text-sm">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            {STATUS_FILTERS.map((s) => (
              <SelectItem key={s} value={s}>
                {t(STATUS_LABEL_KEYS[s])}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
        <Select value={channel} onValueChange={(v) => setChannel(v as typeof channel)}>
          <SelectTrigger className="h-8 w-40 text-sm">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            {CHANNEL_FILTERS.map((c) => (
              <SelectItem key={c} value={c}>
                {t(CHANNEL_LABEL_KEYS[c])}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      </div>

      <Table>
        <TableHeader>
          <TableRow>
            <TableHead>{t("notifLogColMember")}</TableHead>
            <TableHead>{t("notifLogColEvent")}</TableHead>
            <TableHead>{t("notifChannelLabel")}</TableHead>
            <TableHead>{t("notifLogColStatus")}</TableHead>
            <TableHead>{t("notifLogColCost")}</TableHead>
            <TableHead>{t("notifLogColWhen")}</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {rows.map((n) => (
            <TableRow key={n.id}>
              <TableCell>{n.member_name}</TableCell>
              <TableCell>{n.template_key || t("notifLogBroadcastFallback")}</TableCell>
              <TableCell className="capitalize">{t(CHANNEL_LABEL_KEYS[n.channel])}</TableCell>
              <TableCell>
                <Badge variant={n.status === "failed" ? "destructive" : "secondary"}>
                  {t(STATUS_LABEL_KEYS[n.status as (typeof STATUS_FILTERS)[number]])}
                </Badge>
              </TableCell>
              <TableCell className="font-dashboard-mono">
                {formatNpr(n.cost_npr, { symbol: true })}
              </TableCell>
              <TableCell className="font-dashboard-mono text-xs text-muted-foreground">
                {new Date(n.created_at).toLocaleString()}
              </TableCell>
            </TableRow>
          ))}
          {rows.length === 0 && (
            <TableRow>
              <TableCell colSpan={6} className="py-8 text-center text-sm text-muted-foreground">
                {t("notifLogEmptyState")}
              </TableCell>
            </TableRow>
          )}
        </TableBody>
      </Table>
    </div>
  );
}
