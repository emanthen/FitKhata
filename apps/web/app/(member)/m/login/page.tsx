"use client";

import { useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { useTranslations } from "next-intl";
import { sendMemberLoginOtp, verifyMemberLoginOtp } from "@fitkhata/api-client";
import { Phone, ShieldCheck, TriangleAlert } from "lucide-react";

import { setCachedPass } from "@/lib/member/pass";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";

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
    <div className="w-full max-w-sm space-y-5">
      <h1 className="flex items-center gap-2 text-xl font-semibold tracking-tight">
        {step === "phone" ? (
          <Phone size={18} strokeWidth={2} className="text-primary" />
        ) : (
          <ShieldCheck size={18} strokeWidth={2} className="text-primary" />
        )}
        {t("loginTitle")}
      </h1>
      {error && (
        <p className="flex items-center gap-1.5 text-sm text-destructive">
          <TriangleAlert size={14} strokeWidth={2} />
          {error}
        </p>
      )}

      {step === "phone" && (
        <form onSubmit={sendCode} className="space-y-4">
          <div className="space-y-1.5">
            <Label htmlFor="login-phone">{t("loginPhone")}</Label>
            <Input
              id="login-phone"
              type="tel"
              required
              value={phone}
              onChange={(e) => setPhone(e.target.value)}
              className="h-11"
            />
          </div>
          <Button type="submit" disabled={submitting} size="lg" className="h-12 w-full text-base">
            {submitting ? "..." : t("loginSendCode")}
          </Button>
        </form>
      )}

      {step === "code" && (
        <form onSubmit={verify} className="space-y-4">
          <p className="text-sm text-muted-foreground">{t("loginCodeSent")}</p>
          <div className="space-y-1.5">
            <Label htmlFor="login-code">{t("loginCode")}</Label>
            <Input
              id="login-code"
              type="text"
              inputMode="numeric"
              required
              minLength={6}
              maxLength={6}
              value={code}
              onChange={(e) => setCode(e.target.value)}
              className="font-dashboard-mono h-11 text-center text-lg tracking-[0.3em]"
            />
          </div>
          <div className="space-y-1.5">
            <Label htmlFor="login-gym">{t("loginGymCode")}</Label>
            <Input
              id="login-gym"
              type="text"
              required
              value={gymCode}
              onChange={(e) => setGymCode(e.target.value)}
              className="h-11"
            />
          </div>
          <Button type="submit" disabled={submitting} size="lg" className="h-12 w-full text-base">
            {submitting ? "..." : t("loginVerify")}
          </Button>
        </form>
      )}
    </div>
  );
}
