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
import { CircleCheck, Loader2, TriangleAlert, Wallet } from "lucide-react";

import { getCachedPass } from "@/lib/member/pass";
import { formatNpr } from "@/lib/money";
import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";

const PENDING_RENEWAL_KEY = "fitkhata.pending-renewal";
const FONEPAY_POLL_MS = 3000;

const PROVIDERS: { value: RenewalProvider; label: string }[] = [
  { value: "esewa", label: "eSewa" },
  { value: "khalti", label: "Khalti" },
  { value: "fonepay", label: "Fonepay" },
];

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
            <p className="flex items-center justify-center gap-1.5 text-primary">
              <CircleCheck size={16} strokeWidth={2} />
              {t("renewReturnSuccess")}
            </p>
            <Link href="/m" className="inline-block text-sm text-muted-foreground underline">
              {t("renewReturnBackToPass")}
            </Link>
          </>
        ) : (
          <>
            <p className="font-medium">{t("renewFonepayScan")}</p>
            <div className="flex justify-center rounded-xl border bg-card p-4">
              <QRCodeSVG value={fonepayQr.message} size={220} />
            </div>
            <p className="flex items-center justify-center gap-1.5 text-sm text-muted-foreground">
              <Loader2 size={13} strokeWidth={2} className="animate-spin" />
              {t("renewFonepayWaiting")}
            </p>
          </>
        )}
      </div>
    );
  }

  if (redirectForm) {
    return (
      <div className="text-center">
        <p className="flex items-center justify-center gap-1.5 text-muted-foreground">
          <Loader2 size={13} strokeWidth={2} className="animate-spin" />
          {t("renewLoading")}
        </p>
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
    <div className="w-full max-w-sm space-y-5">
      <h1 className="flex items-center gap-2 text-xl font-semibold tracking-tight">
        <Wallet size={18} strokeWidth={2} className="text-primary" />
        {t("renewTitle")}
      </h1>
      {error && (
        <p className="flex items-center gap-1.5 text-sm text-destructive">
          <TriangleAlert size={14} strokeWidth={2} />
          {error}
        </p>
      )}

      {plans === null && (
        <p className="flex items-center gap-1.5 text-sm text-muted-foreground">
          <Loader2 size={13} strokeWidth={2} className="animate-spin" />
          {t("renewLoading")}
        </p>
      )}
      {plans !== null && plans.length === 0 && (
        <p className="text-sm text-muted-foreground">{t("renewNoPlans")}</p>
      )}

      {plans !== null && plans.length > 0 && (
        <form onSubmit={submit} className="space-y-5">
          <div>
            <p className="mb-2 text-sm font-medium">{t("renewChoosePlan")}</p>
            <div className="space-y-2">
              {plans.map((plan) => (
                <label
                  key={plan.id}
                  className={`flex items-center justify-between rounded-xl border px-3.5 py-3 transition-colors ${
                    planId === plan.id ? "border-primary bg-primary/5" : ""
                  }`}
                >
                  <span className="text-sm">
                    {plan.name} <span className="text-muted-foreground">({plan.duration_days}d)</span>
                  </span>
                  <span className="flex items-center gap-2.5">
                    <span className="font-dashboard-mono text-sm">
                      {formatNpr(plan.price_npr, { symbol: true })}
                    </span>
                    <input
                      type="radio"
                      name="plan"
                      value={plan.id}
                      checked={planId === plan.id}
                      onChange={() => setPlanId(plan.id)}
                      className="size-4 accent-primary"
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
                    className="flex items-center justify-between rounded-xl border px-3.5 py-3"
                  >
                    <span className="text-sm">{addon.name}</span>
                    <span className="flex items-center gap-2.5">
                      <span className="font-dashboard-mono text-sm">
                        {formatNpr(addon.price_npr, { symbol: true })}
                      </span>
                      <Checkbox
                        checked={addonIds.includes(addon.id)}
                        onCheckedChange={() => toggleAddon(addon.id)}
                      />
                    </span>
                  </label>
                ))}
              </div>
            </div>
          )}

          <div className="space-y-1.5">
            <Label htmlFor="promo">{t("renewPromoCode")}</Label>
            <Input
              id="promo"
              type="text"
              value={promoCode}
              onChange={(e) => setPromoCode(e.target.value)}
              placeholder={t("renewPromoPlaceholder")}
              className="h-11 uppercase"
            />
          </div>

          <div>
            <p className="mb-2 text-sm font-medium">{t("renewChooseProvider")}</p>
            <div className="flex gap-2">
              {PROVIDERS.map((p) => (
                <label
                  key={p.value}
                  className={`flex flex-1 items-center justify-center gap-1.5 rounded-xl border px-3 py-2.5 text-sm transition-colors ${
                    provider === p.value ? "border-primary bg-primary/5" : ""
                  }`}
                >
                  <input
                    type="radio"
                    name="provider"
                    value={p.value}
                    checked={provider === p.value}
                    onChange={() => setProvider(p.value)}
                    className="size-4 accent-primary"
                  />
                  {p.label}
                </label>
              ))}
            </div>
          </div>

          <Button type="submit" disabled={submitting} size="lg" className="h-12 w-full text-base">
            {submitting ? "..." : t("renewPayButton")}
          </Button>
        </form>
      )}

      <Link href="/m" className="block text-center text-sm text-muted-foreground underline">
        {t("renewBack")}
      </Link>
    </div>
  );
}
