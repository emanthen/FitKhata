"use client";

import { useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { useTranslations } from "next-intl";
import { sendMemberLoginOtp, verifyMemberLoginOtp } from "@fitkhata/api-client";

import { setCachedPass } from "@/lib/member/pass";

type Step = "phone" | "code";

/** Self-service login (FR-8.2) — mints the same signed pass token
 * MemberPassView does, so everything downstream (lib/member/pass.ts's
 * cache, every m/pass/<token>/... endpoint) works unchanged. "Remember
 * device" is just this token's own 2-year expiry + localStorage
 * persistence — nothing else to build for that.
 */
export default function MemberLoginPage() {
  const t = useTranslations("member");
  const router = useRouter();
  const searchParams = useSearchParams();
  const [step, setStep] = useState<Step>("phone");
  const [phone, setPhone] = useState("");
  const [gymCode, setGymCode] = useState(searchParams.get("gym") ?? "");
  const [code, setCode] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  async function sendCode(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setSubmitting(true);
    try {
      await sendMemberLoginOtp(phone);
      setStep("code");
    } catch {
      setError(t("loginError"));
    } finally {
      setSubmitting(false);
    }
  }

  async function verify(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setSubmitting(true);
    try {
      const result = await verifyMemberLoginOtp(phone, code, gymCode);
      setCachedPass({
        member_code: result.member_code,
        full_name: result.full_name,
        gym_code: result.gym_code,
        qr_secret_hex: result.qr_secret_hex,
        token: result.token,
      });
      router.replace("/m");
    } catch (err: unknown) {
      const status = (err as { response?: { status?: number } })?.response?.status;
      if (status === 429) setError(t("loginRateLimited"));
      else if (status === 423) setError(t("loginLocked"));
      else if (status === 404) setError(t("loginNotFound"));
      else if (status === 400) setError(t("loginIncorrectCode"));
      else setError(t("loginError"));
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="w-full max-w-sm space-y-4">
      <h1 className="text-2xl font-semibold">{t("loginTitle")}</h1>
      {error && <p className="text-sm text-red-600">{error}</p>}

      {step === "phone" && (
        <form onSubmit={sendCode} className="space-y-3">
          <label className="block text-sm">
            {t("loginPhone")}
            <input
              type="tel"
              required
              value={phone}
              onChange={(e) => setPhone(e.target.value)}
              className="mt-1 w-full rounded border px-3 py-2"
            />
          </label>
          <button
            type="submit"
            disabled={submitting}
            className="w-full rounded bg-black px-3 py-2 text-white disabled:opacity-50"
          >
            {submitting ? "..." : t("loginSendCode")}
          </button>
        </form>
      )}

      {step === "code" && (
        <form onSubmit={verify} className="space-y-3">
          <p className="text-sm opacity-70">{t("loginCodeSent")}</p>
          <label className="block text-sm">
            {t("loginCode")}
            <input
              type="text"
              inputMode="numeric"
              required
              minLength={6}
              maxLength={6}
              value={code}
              onChange={(e) => setCode(e.target.value)}
              className="mt-1 w-full rounded border px-3 py-2"
            />
          </label>
          <label className="block text-sm">
            {t("loginGymCode")}
            <input
              type="text"
              required
              value={gymCode}
              onChange={(e) => setGymCode(e.target.value)}
              className="mt-1 w-full rounded border px-3 py-2"
            />
          </label>
          <button
            type="submit"
            disabled={submitting}
            className="w-full rounded bg-black px-3 py-2 text-white disabled:opacity-50"
          >
            {submitting ? "..." : t("loginVerify")}
          </button>
        </form>
      )}
    </div>
  );
}
