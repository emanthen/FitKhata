"use client";

import { useState } from "react";
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

const EVENTS: { value: WebhookEvent; label: string }[] = [
  { value: "member.created", label: "Member created" },
  { value: "payment.completed", label: "Payment completed" },
  { value: "checkin.created", label: "Check-in created" },
];

const DELIVERY_VARIANT: Record<string, "default" | "secondary" | "destructive"> = {
  delivered: "default",
  pending: "secondary",
  failed: "destructive",
};

export default function WebhooksSettingsPage() {
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
      setError("Pick at least one event.");
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
      setError("Couldn't save this webhook — check the URL and secret.");
    } finally {
      setSubmitting(false);
    }
  }

  if (planGated) {
    return (
      <div className="max-w-2xl space-y-4">
        <h1 className="text-xl font-semibold tracking-tight">Webhooks</h1>
        <p className="text-sm text-muted-foreground">
          Webhooks are an Enterprise-plan feature. Contact FitKhata support to upgrade.
        </p>
      </div>
    );
  }

  return (
    <div className="max-w-2xl space-y-4">
      <h1 className="text-xl font-semibold tracking-tight">Webhooks</h1>

      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Webhook size={16} strokeWidth={2} className="text-primary" />
            Subscriptions
          </CardTitle>
          <p className="text-sm text-muted-foreground">
            Each delivery is signed — verify{" "}
            <code className="font-dashboard-mono">X-FitKhata-Signature</code> (HMAC-SHA256 of the
            body, using your secret) before trusting a payload.
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
                    {expandedId === sub.id ? "Hide deliveries" : "View deliveries"}
                  </Button>
                </div>
                <p className="text-xs text-muted-foreground">{sub.events.join(", ")}</p>
                {expandedId === sub.id && <DeliveryLog subscriptionId={sub.id} />}
              </li>
            ))}
            {subscriptions.data?.length === 0 && (
              <li className="py-2 text-sm text-muted-foreground">No webhooks yet.</li>
            )}
          </ul>

          {error && <p className="text-sm text-destructive">{error}</p>}
          <form onSubmit={submit} className="space-y-3 border-t pt-3">
            <div className="space-y-1.5">
              <Label htmlFor="webhook-url">Endpoint URL</Label>
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
              <Label htmlFor="webhook-secret">Signing secret</Label>
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
              <Label>Events</Label>
              <div className="flex flex-wrap gap-4">
                {EVENTS.map((event) => (
                  <label key={event.value} className="flex items-center gap-2 text-sm font-normal">
                    <Checkbox
                      checked={events.includes(event.value)}
                      onCheckedChange={(checked) => toggleEvent(event.value, checked === true)}
                    />
                    {event.label}
                  </label>
                ))}
              </div>
            </div>
            <Button type="submit" size="sm" disabled={submitting}>
              {submitting ? "..." : "Add webhook"}
            </Button>
          </form>
        </CardContent>
      </Card>
    </div>
  );
}

function DeliveryLog({ subscriptionId }: { subscriptionId: string }) {
  const deliveries = useQuery({
    queryKey: ["webhook-deliveries", subscriptionId],
    queryFn: () => listWebhookDeliveries(subscriptionId),
  });

  return (
    <ul className="mt-2 space-y-1 rounded-md bg-muted/50 p-2">
      {deliveries.data?.map((d) => (
        <li key={d.id} className="flex items-center justify-between text-xs">
          <span>
            {d.event} · attempt {d.attempt_count}
            {d.response_status ? ` · HTTP ${d.response_status}` : ""}
          </span>
          <Badge variant={DELIVERY_VARIANT[d.status] ?? "secondary"}>{d.status}</Badge>
        </li>
      ))}
      {deliveries.data?.length === 0 && (
        <li className="text-xs text-muted-foreground">No deliveries yet.</li>
      )}
    </ul>
  );
}
