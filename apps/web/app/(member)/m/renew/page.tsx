"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { useTranslations } from "next-intl";
import { QRCodeSVG } from "qrcode.react";
import {
  confirmRenewalCallback,
  initiateRenewal,
  listRenewalAddOns,
  listRenewalPlans,
  type AddOn,
  type RenewalPlan,
  type RenewalProvider,
} from "@fitkhata/api-client";

import { getCachedPass } from "@/lib/member/pass";

const PENDING_RENEWAL_KEY = "fitkhata.pending-renewal";
const FONEPAY_POLL_MS = 3000;

export default function RenewPage() {
  const t = useTranslations("member");
  const router = useRouter();
  const [plans, setPlans] = useState<RenewalPlan[] | null>(null);
  const [addOns, setAddOns] = useState<AddOn[]>([]);
  const [planId, setPlanId] = useState("");
  const [addonIds, setAddonIds] = useState<string[]>([]);
  const [promoCode, setPromoCode] = useState("");
  const [provider, setProvider] = useState<RenewalProvider>("esewa");
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [redirectForm, setRedirectForm] = useState<{
    url: string;
    fields: Record<string, string>;
  } | null>(null);
  const [fonepayQr, setFonepayQr] = useState<{ message: string; paymentId: string } | null>(
    null
  );
  const [fonepayDone, setFonepayDone] = useState(false);

  useEffect(() => {
    const pass = getCachedPass();
    if (!pass) {
      router.replace("/m");
      return;
    }
    listRenewalPlans(pass.token)
      .then((data) => {
        setPlans(data);
        if (data.length > 0) setPlanId(data[0].id);
      })
      .catch(() => setPlans([]));
    listRenewalAddOns(pass.token)
      .then(setAddOns)
      .catch(() => setAddOns([]));
  }, [router]);

  // eSewa wants an auto-submitted POST form, not a simple redirect —
  // render it, then submit it the moment it's in the DOM.
  useEffect(() => {
    if (!redirectForm) return;
    const form = document.getElementById("gateway-redirect-form");
    if (form instanceof HTMLFormElement) form.submit();
  }, [redirectForm]);

  // Fonepay never redirects anywhere — the member stays on this page,
  // scans the QR with their own banking app, and this polls the same
  // callback endpoint eSewa/Khalti's return page uses until it completes.
  useEffect(() => {
    if (!fonepayQr) return;
    const interval = setInterval(async () => {
      try {
        const result = await confirmRenewalCallback({
          provider: "fonepay",
          payment_id: fonepayQr.paymentId,
        });
        if (result.status === "completed") {
          clearInterval(interval);
          setFonepayDone(true);
        }
      } catch {
        // transient network hiccup — the next tick retries
      }
    }, FONEPAY_POLL_MS);
    return () => clearInterval(interval);
  }, [fonepayQr]);

  function toggleAddon(id: string) {
    setAddonIds((prev) => (prev.includes(id) ? prev.filter((a) => a !== id) : [...prev, id]));
  }

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    const pass = getCachedPass();
    if (!pass || !planId) return;
    setError(null);
    setSubmitting(true);
    try {
      const returnUrl = `${window.location.origin}/m/renew/return`;
      const result = await initiateRenewal(pass.token, planId, provider, returnUrl, {
        promoCode,
        addonIds,
      });
      if (provider === "fonepay") {
        setFonepayQr({ message: result.redirect.url, paymentId: result.payment_id });
        return;
      }
      // payment_id travels via localStorage, not the return URL — eSewa's
      // signed form can't be re-signed after the fact to add it, and
      // Khalti's callback doesn't need it from the URL either (the
      // backend already has this payment's pidx stored from initiate).
      localStorage.setItem(
        PENDING_RENEWAL_KEY,
        JSON.stringify({ payment_id: result.payment_id, provider })
      );
      if (result.redirect.method === "POST") {
        setRedirectForm(result.redirect);
      } else {
        window.location.href = result.redirect.url;
      }
    } catch {
      setError(t("renewError"));
      setSubmitting(false);
    }
  }

  if (fonepayQr) {
    return (
      <div className="space-y-4 text-center">
        {fonepayDone ? (
          <>
            <p className="text-green-700">{t("renewReturnSuccess")}</p>
            <Link href="/m" className="inline-block text-sm underline opacity-70">
              {t("renewReturnBackToPass")}
            </Link>
          </>
        ) : (
          <>
            <p className="font-medium">{t("renewFonepayScan")}</p>
            <div className="flex justify-center">
              <QRCodeSVG value={fonepayQr.message} size={220} />
            </div>
            <p className="text-sm opacity-70">{t("renewFonepayWaiting")}</p>
          </>
        )}
      </div>
    );
  }

  if (redirectForm) {
    return (
      <div className="text-center">
        <p className="opacity-70">{t("renewLoading")}</p>
        <form
          id="gateway-redirect-form"
          action={redirectForm.url}
          method="POST"
          className="hidden"
        >
          {Object.entries(redirectForm.fields).map(([key, value]) => (
            <input key={key} type="hidden" name={key} value={value} />
          ))}
        </form>
      </div>
    );
  }

  return (
    <div className="w-full max-w-sm space-y-4">
      <h1 className="text-2xl font-semibold">{t("renewTitle")}</h1>
      {error && <p className="text-sm text-red-600">{error}</p>}

      {plans === null && <p className="opacity-70">{t("renewLoading")}</p>}
      {plans !== null && plans.length === 0 && <p className="opacity-70">{t("renewNoPlans")}</p>}

      {plans !== null && plans.length > 0 && (
        <form onSubmit={submit} className="space-y-4">
          <div>
            <p className="mb-2 text-sm font-medium">{t("renewChoosePlan")}</p>
            <div className="space-y-2">
              {plans.map((plan) => (
                <label
                  key={plan.id}
                  className="flex items-center justify-between rounded border px-3 py-2"
                >
                  <span>
                    {plan.name} <span className="opacity-60">({plan.duration_days}d)</span>
                  </span>
                  <span className="flex items-center gap-2">
                    <span>NPR {plan.price_npr}</span>
                    <input
                      type="radio"
                      name="plan"
                      value={plan.id}
                      checked={planId === plan.id}
                      onChange={() => setPlanId(plan.id)}
                    />
                  </span>
                </label>
              ))}
            </div>
          </div>

          {addOns.length > 0 && (
            <div>
              <p className="mb-2 text-sm font-medium">{t("renewAddOns")}</p>
              <div className="space-y-2">
                {addOns.map((addon) => (
                  <label
                    key={addon.id}
                    className="flex items-center justify-between rounded border px-3 py-2"
                  >
                    <span>{addon.name}</span>
                    <span className="flex items-center gap-2">
                      <span>NPR {addon.price_npr}</span>
                      <input
                        type="checkbox"
                        checked={addonIds.includes(addon.id)}
                        onChange={() => toggleAddon(addon.id)}
                      />
                    </span>
                  </label>
                ))}
              </div>
            </div>
          )}

          <label className="block text-sm">
            {t("renewPromoCode")}
            <input
              type="text"
              value={promoCode}
              onChange={(e) => setPromoCode(e.target.value)}
              placeholder={t("renewPromoPlaceholder")}
              className="mt-1 w-full rounded border px-3 py-2 uppercase"
            />
          </label>

          <div>
            <p className="mb-2 text-sm font-medium">{t("renewChooseProvider")}</p>
            <div className="flex gap-3">
              {(
                [
                  { value: "esewa", label: "eSewa" },
                  { value: "khalti", label: "Khalti" },
                  { value: "fonepay", label: "Fonepay" },
                ] satisfies { value: RenewalProvider; label: string }[]
              ).map((p) => (
                <label key={p.value} className="flex items-center gap-1.5 rounded border px-3 py-2">
                  <input
                    type="radio"
                    name="provider"
                    value={p.value}
                    checked={provider === p.value}
                    onChange={() => setProvider(p.value)}
                  />
                  <span>{p.label}</span>
                </label>
              ))}
            </div>
          </div>

          <button
            type="submit"
            disabled={submitting}
            className="w-full rounded bg-black px-3 py-2 text-white disabled:opacity-50"
          >
            {submitting ? "..." : t("renewPayButton")}
          </button>
        </form>
      )}

      <Link href="/m" className="block text-center text-sm underline opacity-70">
        {t("renewBack")}
      </Link>
    </div>
  );
}
