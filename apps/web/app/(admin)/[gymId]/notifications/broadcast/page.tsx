"use client";

import { useState } from "react";
import {
  estimateBroadcast,
  sendBroadcast,
  type BroadcastSegment,
  type NotificationChannel,
} from "@fitkhata/api-client";
import { CircleCheck, Megaphone, TriangleAlert } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { formatNpr } from "@/lib/money";

const SEGMENTS: { value: BroadcastSegment; label: string; needsValue: boolean }[] = [
  { value: "expired", label: "Expired members", needsValue: false },
  { value: "red_list", label: "Red list", needsValue: false },
  { value: "plan", label: "On a specific plan", needsValue: true },
  { value: "gender", label: "Gender", needsValue: true },
  { value: "tag", label: "Tag", needsValue: true },
];

const CHANNELS: { value: NotificationChannel; label: string }[] = [
  { value: "sms", label: "SMS" },
  { value: "whatsapp", label: "WhatsApp" },
  { value: "push", label: "Push" },
  { value: "email", label: "Email" },
];

export default function BroadcastComposerPage() {
  const [segment, setSegment] = useState<BroadcastSegment>("expired");
  const [segmentValue, setSegmentValue] = useState("");
  const [channel, setChannel] = useState<NotificationChannel>("sms");
  const [bodyNe, setBodyNe] = useState("");
  const [bodyEn, setBodyEn] = useState("");
  const [estimate, setEstimate] = useState<{ recipient_count: number; cost_npr: string } | null>(
    null
  );
  const [sending, setSending] = useState(false);
  const [sent, setSent] = useState<{ recipient_count: number; cost_npr: string } | null>(null);
  const [error, setError] = useState<string | null>(null);

  const needsValue = SEGMENTS.find((s) => s.value === segment)?.needsValue ?? false;

  function resetEstimate() {
    setEstimate(null);
    setSent(null);
  }

  async function preview(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    try {
      const result = await estimateBroadcast({ segment, segment_value: segmentValue, channel });
      setEstimate(result);
    } catch {
      setError("Couldn't estimate this broadcast.");
    }
  }

  async function confirm() {
    setSending(true);
    setError(null);
    try {
      const broadcast = await sendBroadcast({
        segment,
        segment_value: segmentValue,
        channel,
        body_ne: bodyNe,
        body_en: bodyEn,
      });
      setSent({ recipient_count: broadcast.recipient_count, cost_npr: broadcast.cost_npr });
      setEstimate(null);
    } catch {
      setError("Couldn't send this broadcast.");
    } finally {
      setSending(false);
    }
  }

  if (sent) {
    return (
      <div className="max-w-md space-y-4">
        <h1 className="flex items-center gap-2 text-xl font-semibold tracking-tight">
          <CircleCheck size={18} strokeWidth={2} className="text-primary" />
          Broadcast sent
        </h1>
        <p className="text-sm">
          Reached {sent.recipient_count} member{sent.recipient_count === 1 ? "" : "s"} for{" "}
          {formatNpr(sent.cost_npr, { symbol: true })}.
        </p>
        <Button onClick={() => setSent(null)}>Send another</Button>
      </div>
    );
  }

  return (
    <div className="max-w-xl space-y-4">
      <h1 className="flex items-center gap-2 text-xl font-semibold tracking-tight">
        <Megaphone size={18} strokeWidth={2} className="text-primary" />
        Broadcast
      </h1>
      {error && (
        <p className="flex items-center gap-1.5 text-sm text-destructive">
          <TriangleAlert size={14} strokeWidth={2} />
          {error}
        </p>
      )}

      <Card>
        <CardContent>
          <form onSubmit={preview} className="space-y-4">
            <div className="flex flex-wrap gap-2">
              <div className="space-y-1.5">
                <Label htmlFor="segment">Segment</Label>
                <Select
                  value={segment}
                  onValueChange={(v) => {
                    setSegment(v as BroadcastSegment);
                    resetEstimate();
                  }}
                >
                  <SelectTrigger id="segment" className="h-8 w-44 text-sm">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    {SEGMENTS.map((s) => (
                      <SelectItem key={s.value} value={s.value}>
                        {s.label}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
              {needsValue && (
                <div className="space-y-1.5">
                  <Label htmlFor="segment-value">Value</Label>
                  <Input
                    id="segment-value"
                    value={segmentValue}
                    onChange={(e) => {
                      setSegmentValue(e.target.value);
                      resetEstimate();
                    }}
                    className="h-8 w-40"
                  />
                </div>
              )}
              <div className="space-y-1.5">
                <Label htmlFor="channel">Channel</Label>
                <Select
                  value={channel}
                  onValueChange={(v) => {
                    setChannel(v as NotificationChannel);
                    resetEstimate();
                  }}
                >
                  <SelectTrigger id="channel" className="h-8 w-32 text-sm">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    {CHANNELS.map((c) => (
                      <SelectItem key={c.value} value={c.value}>
                        {c.label}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
            </div>

            <div className="space-y-1.5">
              <Label htmlFor="body-ne">Message (Nepali)</Label>
              <textarea
                id="body-ne"
                value={bodyNe}
                onChange={(e) => setBodyNe(e.target.value)}
                className="h-20 w-full rounded-lg border border-input bg-transparent p-2.5 text-sm outline-none focus-visible:border-ring focus-visible:ring-3 focus-visible:ring-ring/50"
                required
              />
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="body-en">Message (English)</Label>
              <textarea
                id="body-en"
                value={bodyEn}
                onChange={(e) => setBodyEn(e.target.value)}
                className="h-20 w-full rounded-lg border border-input bg-transparent p-2.5 text-sm outline-none focus-visible:border-ring focus-visible:ring-3 focus-visible:ring-ring/50"
                required
              />
            </div>

            <Button type="submit" size="sm">
              Preview
            </Button>
          </form>
        </CardContent>
      </Card>

      {estimate && (
        <Card>
          <CardContent className="space-y-2">
            <p className="font-dashboard-mono text-sm font-medium">
              {estimate.recipient_count} recipient{estimate.recipient_count === 1 ? "" : "s"}{" "}
              &middot; {formatNpr(estimate.cost_npr, { symbol: true })}
            </p>
            <Button onClick={confirm} disabled={sending} size="sm">
              {sending ? "..." : "Send broadcast"}
            </Button>
          </CardContent>
        </Card>
      )}
    </div>
  );
}
