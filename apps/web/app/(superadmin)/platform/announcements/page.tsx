"use client";

import { useState } from "react";
import { useTranslations } from "next-intl";
import { broadcastAnnouncement } from "@fitkhata/api-client";
import { Megaphone, Send } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";

export default function AnnouncementsPage() {
  const t = useTranslations("admin");
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
      setResult(t("platformAnnouncementsSentResult", { count: res.sent }));
      setSubject("");
      setBody("");
    } catch {
      setResult(t("platformAnnouncementsFailed"));
    } finally {
      setSending(false);
    }
  }

  return (
    <div className="max-w-xl space-y-6">
      <div>
        <h1 className="flex items-center gap-2 text-xl font-semibold tracking-tight">
          <Megaphone size={18} strokeWidth={2} className="text-primary" />
          {t("platformAnnouncementsTitle")}
        </h1>
        <p className="mt-1 text-sm text-muted-foreground">{t("platformAnnouncementsBody")}</p>
      </div>

      <Card>
        <CardContent className="space-y-4">
          <div className="space-y-1.5">
            <Label htmlFor="subject">{t("platformAnnouncementsSubjectLabel")}</Label>
            <Input id="subject" value={subject} onChange={(e) => setSubject(e.target.value)} />
          </div>
          <div className="space-y-1.5">
            <Label htmlFor="body">{t("platformAnnouncementsMessageLabel")}</Label>
            <Textarea id="body" rows={6} value={body} onChange={(e) => setBody(e.target.value)} />
          </div>
          <Button onClick={send} disabled={sending}>
            <Send size={14} strokeWidth={2} data-icon="inline-start" />
            {sending ? t("platformAnnouncementsSending") : t("platformAnnouncementsSendButton")}
          </Button>
          {result && <p className="text-sm text-muted-foreground">{result}</p>}
        </CardContent>
      </Card>
    </div>
  );
}
