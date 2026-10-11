"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { useTranslations } from "next-intl";
import { submitMemberFreezeRequest } from "@fitkhata/api-client";
import { CircleCheck, Snowflake, TriangleAlert } from "lucide-react";

import { getCachedPass } from "@/lib/member/pass";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";

export default function MemberFreezeRequestPage() {
  const t = useTranslations("member");
  const router = useRouter();
  const [startDate, setStartDate] = useState("");
  const [endDate, setEndDate] = useState("");
  const [reason, setReason] = useState("");
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
      await submitMemberFreezeRequest(pass.token, {
        start_date: startDate,
        end_date: endDate,
        reason,
      });
      setSubmitted(true);
    } catch {
      setError(t("freezeError"));
    } finally {
      setSubmitting(false);
    }
  }

  if (submitted) {
    return (
      <p className="flex items-center justify-center gap-1.5 text-sm text-primary">
        <CircleCheck size={16} strokeWidth={2} />
        {t("freezeSubmitted")}
      </p>
    );
  }

  return (
    <div className="w-full max-w-sm space-y-5">
      <h1 className="flex items-center gap-2 text-xl font-semibold tracking-tight">
        <Snowflake size={18} strokeWidth={2} className="text-primary" />
        {t("freezeTitle")}
      </h1>
      {error && (
        <p className="flex items-center gap-1.5 text-sm text-destructive">
          <TriangleAlert size={14} strokeWidth={2} />
          {error}
        </p>
      )}

      <form onSubmit={submit} className="space-y-4">
        <div className="space-y-1.5">
          <Label htmlFor="freeze-start">{t("freezeStart")}</Label>
          <Input
            id="freeze-start"
            type="date"
            required
            value={startDate}
            onChange={(e) => setStartDate(e.target.value)}
            className="h-11"
          />
        </div>
        <div className="space-y-1.5">
          <Label htmlFor="freeze-end">{t("freezeEnd")}</Label>
          <Input
            id="freeze-end"
            type="date"
            required
            value={endDate}
            onChange={(e) => setEndDate(e.target.value)}
            className="h-11"
          />
        </div>
        <div className="space-y-1.5">
          <Label htmlFor="freeze-reason">{t("freezeReason")}</Label>
          <textarea
            id="freeze-reason"
            required
            value={reason}
            onChange={(e) => setReason(e.target.value)}
            rows={3}
            className="w-full rounded-xl border border-input bg-transparent p-3 text-sm outline-none focus-visible:border-ring focus-visible:ring-3 focus-visible:ring-ring/50"
          />
        </div>
        <Button type="submit" disabled={submitting} size="lg" className="h-12 w-full text-base">
          {submitting ? "..." : t("freezeSubmit")}
        </Button>
      </form>
    </div>
  );
}
