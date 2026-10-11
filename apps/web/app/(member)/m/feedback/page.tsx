"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { useTranslations } from "next-intl";
import { submitMemberFeedback } from "@fitkhata/api-client";
import { CircleCheck, MessageSquareText, TriangleAlert } from "lucide-react";

import { getCachedPass } from "@/lib/member/pass";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";

export default function MemberFeedbackPage() {
  const t = useTranslations("member");
  const router = useRouter();
  const [message, setMessage] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [submitted, setSubmitted] = useState(false);
  const [submitting, setSubmitting] = useState(false);

  useEffect(() => {
    if (!getCachedPass()) router.replace("/m");
  }, [router]);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    const pass = getCachedPass();
    if (!pass) return;
    setError(null);
    setSubmitting(true);
    try {
      await submitMemberFeedback(pass.token, message);
      setSubmitted(true);
    } catch {
      setError(t("feedbackError"));
    } finally {
      setSubmitting(false);
    }
  }

  if (submitted) {
    return (
      <p className="flex items-center justify-center gap-1.5 text-sm text-primary">
        <CircleCheck size={16} strokeWidth={2} />
        {t("feedbackSubmitted")}
      </p>
    );
  }

  return (
    <div className="w-full max-w-sm space-y-5">
      <h1 className="flex items-center gap-2 text-xl font-semibold tracking-tight">
        <MessageSquareText size={18} strokeWidth={2} className="text-primary" />
        {t("feedbackTitle")}
      </h1>
      {error && (
        <p className="flex items-center gap-1.5 text-sm text-destructive">
          <TriangleAlert size={14} strokeWidth={2} />
          {error}
        </p>
      )}

      <form onSubmit={submit} className="space-y-4">
        <div className="space-y-1.5">
          <Label htmlFor="feedback-message">{t("feedbackMessage")}</Label>
          <textarea
            id="feedback-message"
            required
            value={message}
            onChange={(e) => setMessage(e.target.value)}
            rows={4}
            className="w-full rounded-xl border border-input bg-transparent p-3 text-sm outline-none focus-visible:border-ring focus-visible:ring-3 focus-visible:ring-ring/50"
          />
        </div>
        <Button type="submit" disabled={submitting} size="lg" className="h-12 w-full text-base">
          {submitting ? "..." : t("feedbackSubmit")}
        </Button>
      </form>
    </div>
  );
}
