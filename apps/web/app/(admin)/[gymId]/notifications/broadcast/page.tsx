"use client";

import { useState } from "react";
import {
  estimateBroadcast,
  sendBroadcast,
  type BroadcastSegment,
  type NotificationChannel,
} from "@fitkhata/api-client";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
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
      <div className="max-w-md space-y-3">
        <h1 className="text-2xl font-semibold">Broadcast sent</h1>
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
      <h1 className="text-2xl font-semibold">Broadcast</h1>
      {error && <p className="text-sm text-red-600">{error}</p>}

      <form onSubmit={preview} className="space-y-3 rounded border p-3">
        <div className="flex flex-wrap gap-2">
          <div className="space-y-1">
            <Label htmlFor="segment">Segment</Label>
            <select
              id="segment"
              value={segment}
              onChange={(e) => {
                setSegment(e.target.value as BroadcastSegment);
                resetEstimate();
              }}
              className="h-9 rounded border px-2 text-sm"
            >
              {SEGMENTS.map((s) => (
                <option key={s.value} value={s.value}>
                  {s.label}
                </option>
              ))}
            </select>
          </div>
          {needsValue && (
            <div className="space-y-1">
              <Label htmlFor="segment-value">Value</Label>
              <Input
                id="segment-value"
                value={segmentValue}
                onChange={(e) => {
                  setSegmentValue(e.target.value);
                  resetEstimate();
                }}
                className="w-40"
              />
            </div>
          )}
          <div className="space-y-1">
            <Label htmlFor="channel">Channel</Label>
            <select
              id="channel"
              value={channel}
              onChange={(e) => {
                setChannel(e.target.value as NotificationChannel);
                resetEstimate();
              }}
              className="h-9 rounded border px-2 text-sm"
            >
              {CHANNELS.map((c) => (
                <option key={c.value} value={c.value}>
                  {c.label}
                </option>
              ))}
            </select>
          </div>
        </div>

        <div className="space-y-1">
          <Label htmlFor="body-ne">Message (Nepali)</Label>
          <textarea
            id="body-ne"
            value={bodyNe}
            onChange={(e) => setBodyNe(e.target.value)}
            className="h-20 w-full rounded border p-2 text-sm"
            required
          />
        </div>
        <div className="space-y-1">
          <Label htmlFor="body-en">Message (English)</Label>
          <textarea
            id="body-en"
            value={bodyEn}
            onChange={(e) => setBodyEn(e.target.value)}
            className="h-20 w-full rounded border p-2 text-sm"
            required
          />
        </div>

        <Button type="submit">Preview</Button>
      </form>

      {estimate && (
        <div className="space-y-2 rounded border p-3">
          <p className="text-sm font-medium">
            {estimate.recipient_count} recipient{estimate.recipient_count === 1 ? "" : "s"} ·{" "}
            {formatNpr(estimate.cost_npr, { symbol: true })}
          </p>
          <Button onClick={confirm} disabled={sending}>
            {sending ? "..." : "Send broadcast"}
          </Button>
        </div>
      )}
    </div>
  );
}
