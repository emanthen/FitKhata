"use client";

import { useState } from "react";
import { broadcastAnnouncement } from "@fitkhata/api-client";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";

export default function AnnouncementsPage() {
  const [subject, setSubject] = useState("");
  const [body, setBody] = useState("");
  const [result, setResult] = useState<string | null>(null);
  const [sending, setSending] = useState(false);

  async function send() {
    if (!subject.trim() || !body.trim()) return;
    setSending(true);
    setResult(null);
    try {
      const res = await broadcastAnnouncement(subject.trim(), body.trim());
      setResult(`Sent to ${res.sent} owner(s).`);
      setSubject("");
      setBody("");
    } catch {
      setResult("Failed to send.");
    } finally {
      setSending(false);
    }
  }

  return (
    <div className="max-w-xl space-y-6">
      <h1 className="text-2xl font-semibold">Announcements</h1>
      <p className="text-sm opacity-70">
        Sends immediately by email/WhatsApp to every active owner across every org.
      </p>

      <div className="space-y-2">
        <Label htmlFor="subject">Subject</Label>
        <Input id="subject" value={subject} onChange={(e) => setSubject(e.target.value)} />
      </div>
      <div className="space-y-2">
        <Label htmlFor="body">Message</Label>
        <Textarea id="body" rows={6} value={body} onChange={(e) => setBody(e.target.value)} />
      </div>
      <Button onClick={send} disabled={sending}>
        {sending ? "Sending..." : "Broadcast to all owners"}
      </Button>
      {result && <p className="text-sm opacity-80">{result}</p>}
    </div>
  );
}
