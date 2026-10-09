"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { useTranslations } from "next-intl";
import { submitMemberFeedback } from "@fitkhata/api-client";

import { getCachedPass } from "@/lib/member/pass";

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
    return <p className="text-sm text-green-700">{t("feedbackSubmitted")}</p>;
  }

  return (
    <div className="w-full max-w-sm space-y-4">
      <h1 className="text-2xl font-semibold">{t("feedbackTitle")}</h1>
      {error && <p className="text-sm text-red-600">{error}</p>}

      <form onSubmit={submit} className="space-y-3">
        <label className="block text-sm">
          {t("feedbackMessage")}
          <textarea
            required
            value={message}
            onChange={(e) => setMessage(e.target.value)}
            className="mt-1 w-full rounded border px-3 py-2"
            rows={4}
          />
        </label>
        <button
          type="submit"
          disabled={submitting}
          className="w-full rounded bg-black px-3 py-2 text-white disabled:opacity-50"
        >
          {submitting ? "..." : t("feedbackSubmit")}
        </button>
      </form>
    </div>
  );
}
