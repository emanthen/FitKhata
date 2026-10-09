"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { useTranslations } from "next-intl";
import { submitMemberFreezeRequest } from "@fitkhata/api-client";

import { getCachedPass } from "@/lib/member/pass";

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
    return <p className="text-sm text-green-700">{t("freezeSubmitted")}</p>;
  }

  return (
    <div className="w-full max-w-sm space-y-4">
      <h1 className="text-2xl font-semibold">{t("freezeTitle")}</h1>
      {error && <p className="text-sm text-red-600">{error}</p>}

      <form onSubmit={submit} className="space-y-3">
        <label className="block text-sm">
          {t("freezeStart")}
          <input
            type="date"
            required
            value={startDate}
            onChange={(e) => setStartDate(e.target.value)}
            className="mt-1 w-full rounded border px-3 py-2"
          />
        </label>
        <label className="block text-sm">
          {t("freezeEnd")}
          <input
            type="date"
            required
            value={endDate}
            onChange={(e) => setEndDate(e.target.value)}
            className="mt-1 w-full rounded border px-3 py-2"
          />
        </label>
        <label className="block text-sm">
          {t("freezeReason")}
          <textarea
            required
            value={reason}
            onChange={(e) => setReason(e.target.value)}
            className="mt-1 w-full rounded border px-3 py-2"
            rows={3}
          />
        </label>
        <button
          type="submit"
          disabled={submitting}
          className="w-full rounded bg-black px-3 py-2 text-white disabled:opacity-50"
        >
          {submitting ? "..." : t("freezeSubmit")}
        </button>
      </form>
    </div>
  );
}
