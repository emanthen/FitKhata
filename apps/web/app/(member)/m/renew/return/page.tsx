"use client";

import { useEffect, useState } from "react";
import { useSearchParams } from "next/navigation";
import Link from "next/link";
import { useTranslations } from "next-intl";
import { confirmRenewalCallback } from "@fitkhata/api-client";

const PENDING_RENEWAL_KEY = "fitkhata.pending-renewal";
const POLL_MS = 4000;
const MAX_POLLS = 15; // ~1 minute of polling before leaving it on "pending"

type Outcome = "processing" | "completed" | "pending" | "error";

export default function RenewReturnPage() {
  const t = useTranslations("member");
  const searchParams = useSearchParams();
  const [outcome, setOutcome] = useState<Outcome>("processing");

  useEffect(() => {
    const raw = localStorage.getItem(PENDING_RENEWAL_KEY);
    if (!raw) {
      setOutcome("error");
      return;
    }

    let pending: { payment_id: string; provider: "esewa" | "khalti" };
    try {
      pending = JSON.parse(raw);
    } catch {
      setOutcome("error");
      return;
    }

    const payload: Parameters<typeof confirmRenewalCallback>[0] = {
      provider: pending.provider,
      payment_id: pending.payment_id,
    };
    if (pending.provider === "esewa") {
      // eSewa appends this itself on redirect back to our return_url.
      const data = searchParams.get("data");
      if (!data) {
        setOutcome("error");
        return;
      }
      payload.data = data;
    }
    // Khalti needs nothing from the URL — the backend already has this
    // payment's pidx stored from the initiate step.

    let cancelled = false;
    let attempts = 0;

    // Usually resolves on the very first call (the gateway already
    // settled it before redirecting back) — this loop only matters for
    // the rarer case where Khalti/eSewa report the payment as still
    // settling at the moment the member's browser lands back here.
    async function poll() {
      attempts += 1;
      try {
        const result = await confirmRenewalCallback(payload);
        if (cancelled) return;
        if (result.status === "completed") {
          localStorage.removeItem(PENDING_RENEWAL_KEY);
          setOutcome("completed");
          return;
        }
        if (attempts >= MAX_POLLS) {
          setOutcome("pending");
          return;
        }
        setOutcome("pending");
        setTimeout(poll, POLL_MS);
      } catch {
        if (!cancelled) setOutcome("error");
      }
    }

    poll();
    return () => {
      cancelled = true;
    };
  }, [searchParams]);

  const message =
    outcome === "processing"
      ? t("renewReturnProcessing")
      : outcome === "completed"
        ? t("renewReturnSuccess")
        : outcome === "pending"
          ? t("renewReturnPending")
          : t("renewReturnError");

  return (
    <div className="w-full max-w-sm space-y-4 text-center">
      <p className={outcome === "error" ? "text-red-600" : undefined}>{message}</p>
      {outcome !== "processing" && (
        <Link href="/m" className="inline-block text-sm underline opacity-70">
          {t("renewReturnBackToPass")}
        </Link>
      )}
    </div>
  );
}
