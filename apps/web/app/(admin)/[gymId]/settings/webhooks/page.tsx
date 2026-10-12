"use client";

import { useState } from "react";
import { useTranslations } from "next-intl";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import {
  createWebhookSubscription,
  listWebhookDeliveries,
  listWebhookSubscriptions,
  type WebhookEvent,
} from "@fitkhata/api-client";
import { Webhook } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Checkbox } from "@/components/ui/checkbox";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";

const EVENTS: { value: WebhookEvent; labelKey: string }[] = [
  { value: "member.created", labelKey: "notifWebhookEventMemberCreated" },
  { value: "payment.completed", labelKey: "notifWebhookEventPaymentCompleted" },
  { value: "checkin.created", labelKey: "notifWebhookEventCheckinCreated" },
];
const EVENT_LABEL_KEYS: Record<string, string> = Object.fromEntries(
  EVENTS.map((e) => [e.value, e.labelKey])
);

const DELIVERY_VARIANT: Record<string, "default" | "secondary" | "destructive"> = {
  delivered: "default",
  pending: "secondary",
  failed: "destructive",
};
const DELIVERY_STATUS_LABEL_KEYS: Record<string, string> = {
  delivered: "notifStatusDelivered",
  pending: "notifWebhookStatusPending",
  failed: "notifStatusFailed",
};

export default function WebhooksSettingsPage() {
  const t = useTranslations("admin");
  const queryClient = useQueryClient();
  const subscriptions = useQuery({
    queryKey: ["webhook-subscriptions"],
    queryFn: listWebhookSubscriptions,
    retry: false,
  });

  const [url, setUrl] = useState("");
  const [secret, setSecret] = useState("");
  const [events, setEvents] = useState<WebhookEvent[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [expandedId, setExpandedId] = useState<string | null>(null);

  const planGated = (subscriptions.error as { response?: { status?: number } } | undefined)
    ?.response?.status === 403;

  function toggleEvent(event: WebhookEvent, checked: boolean) {
    setEvents((prev) => (checked ? [...prev, event] : prev.filter((e) => e !== event)));
  }

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    if (events.length === 0) {
      setError(t("notifWebhookPickEventError"));
      return;
    }
    setSubmitting(true);
    try {
      await createWebhookSubscription({ url, events, secret });
      setUrl("");
      setSecret("");
      setEvents([]);
      queryClient.invalidateQueries({ queryKey: ["webhook-subscriptions"] });
    } catch {
      setError(t("notifWebhookSaveError"));
    } finally {
      setSubmitting(false);
    }
  }

  if (planGated) {
    return (
      <div className="max-w-2xl space-y-4">
        <h1 className="text-xl font-semibold tracking-tight">{t("settingsWebhooks")}</h1>
        <p className="text-sm text-muted-foreground">{t("notifWebhookPlanGated")}</p>
      </div>
    );
  }

  return (
    <div className="max-w-2xl space-y-4">
      <h1 className="text-xl font-semibold tracking-tight">{t("settingsWebhooks")}</h1>

      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Webhook size={16} strokeWidth={2} className="text-primary" />
            {t("notifWebhookSubscriptions")}
          </CardTitle>
          <p className="text-sm text-muted-foreground">
            {t("notifWebhookSignedBody")}{" "}
            <code className="font-dashboard-mono">X-FitKhata-Signature</code>{" "}
            {t("notifWebhookSignedBodySuffix")}
          </p>
        </CardHeader>
        <CardContent className="space-y-3">
          <ul className="divide-y">
            {subscriptions.data?.map((sub) => (
              <li key={sub.id} className="py-2 text-sm">
                <div className="flex items-center justify-between">
                  <span className="truncate">{sub.url}</span>
                  <Button
                    variant="ghost"
                    size="sm"
                    className="h-7 text-xs"
                    onClick={() => setExpandedId(expandedId === sub.id ? null : sub.id)}
                  >
                    {expandedId === sub.id
                      ? t("notifWebhookHideDeliveries")
                      : t("notifWebhookViewDeliveries")}
                  </Button>
                </div>
                <p className="text-xs text-muted-foreground">
                  {sub.events.map((e) => t(EVENT_LABEL_KEYS[e] ?? "")).join(", ")}
                </p>
                {expandedId === sub.id && <DeliveryLog subscriptionId={sub.id} />}
              </li>
            ))}
            {subscriptions.data?.length === 0 && (
              <li className="py-2 text-sm text-muted-foreground">{t("notifWebhookNoneYet")}</li>
            )}
          </ul>

          {error && <p className="text-sm text-destructive">{error}</p>}
          <form onSubmit={submit} className="space-y-3 border-t pt-3">
            <div className="space-y-1.5">
              <Label htmlFor="webhook-url">{t("notifWebhookEndpointUrl")}</Label>
              <Input
                id="webhook-url"
                type="url"
                value={url}
                onChange={(e) => setUrl(e.target.value)}
                placeholder="https://example.com/hooks/fitkhata"
                className="h-8 w-full"
                required
              />
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="webhook-secret">{t("notifWebhookSigningSecret")}</Label>
              <Input
                id="webhook-secret"
                type="password"
                value={secret}
                onChange={(e) => setSecret(e.target.value)}
                className="h-8 w-full"
                required
              />
            </div>
            <div className="space-y-1.5">
              <Label>{t("notifWebhookEventsLabel")}</Label>
              <div className="flex flex-wrap gap-4">
                {EVENTS.map((event) => (
                  <label key={event.value} className="flex items-center gap-2 text-sm font-normal">
                    <Checkbox
                      checked={events.includes(event.value)}
                      onCheckedChange={(checked) => toggleEvent(event.value, checked === true)}
                    />
                    {t(event.labelKey)}
                  </label>
                ))}
              </div>
            </div>
            <Button type="submit" size="sm" disabled={submitting}>
              {submitting ? "..." : t("notifWebhookAddButton")}
            </Button>
          </form>
        </CardContent>
      </Card>
    </div>
  );
}

function DeliveryLog({ subscriptionId }: { subscriptionId: string }) {
  const t = useTranslations("admin");
  const deliveries = useQuery({
    queryKey: ["webhook-deliveries", subscriptionId],
    queryFn: () => listWebhookDeliveries(subscriptionId),
  });

  return (
    <ul className="mt-2 space-y-1 rounded-md bg-muted/50 p-2">
      {deliveries.data?.map((d) => (
        <li key={d.id} className="flex items-center justify-between text-xs">
          <span>
            {t(EVENT_LABEL_KEYS[d.event] ?? "")} ·{" "}
            {t("notifWebhookAttempt", { count: d.attempt_count })}
            {d.response_status ? ` · HTTP ${d.response_status}` : ""}
          </span>
          <Badge variant={DELIVERY_VARIANT[d.status] ?? "secondary"}>
            {t(DELIVERY_STATUS_LABEL_KEYS[d.status] ?? "")}
          </Badge>
        </li>
      ))}
      {deliveries.data?.length === 0 && (
        <li className="text-xs text-muted-foreground">{t("notifWebhookNoDeliveriesYet")}</li>
      )}
    </ul>
  );
}
