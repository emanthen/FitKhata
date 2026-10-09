"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { useTranslations } from "next-intl";
import { QRCodeSVG } from "qrcode.react";
import {
  getMemberAttendanceCalendar,
  getMemberMembershipStatus,
  getMemberNextClass,
  type MemberMembershipStatus,
} from "@fitkhata/api-client";

import { hexToBytes, payloadFor } from "@/lib/qr";
import { getCachedPass, type CachedPass } from "@/lib/member/pass";
import { pushSupported, subscribeToPushNotifications } from "@/lib/push";
import { adIsoToBsLabel } from "@/lib/bs-calendar";
import { ReferralCard } from "@/components/member/referral-card";

const WINDOW_SECONDS = 30;
const RING_RADIUS = 36;
const RING_CIRCUMFERENCE = 2 * Math.PI * RING_RADIUS;
const QR_SIZE = 220;

export default function MemberPassPage() {
  const t = useTranslations("member");
  const router = useRouter();
  const [pass, setPass] = useState<CachedPass | null>(null);
  const [ready, setReady] = useState(false);
  const [payload, setPayload] = useState<string | null>(null);
  const [secondsLeft, setSecondsLeft] = useState(WINDOW_SECONDS);
  const [pushState, setPushState] = useState<"idle" | "enabled" | "error">("idle");
  const [status, setStatus] = useState<MemberMembershipStatus | null>(null);
  const [streak, setStreak] = useState(0);
  const [nextClass, setNextClass] = useState<{ class_name: string; starts_at: string } | null>(
    null
  );

  useEffect(() => {
    setPass(getCachedPass());
    setReady(true);
  }, []);

  useEffect(() => {
    if (!ready) return;
    if (!pass) {
      router.replace("/m/login");
    }
  }, [ready, pass, router]);

  useEffect(() => {
    if (!pass) return;
    getMemberMembershipStatus(pass.token).then(setStatus).catch(() => setStatus(null));
    getMemberAttendanceCalendar(pass.token)
      .then((data) => setStreak(data.current_streak))
      .catch(() => setStreak(0));
    getMemberNextClass(pass.token).then(setNextClass).catch(() => setNextClass(null));
  }, [pass]);

  useEffect(() => {
    if (!pass) return;
    const { gym_code: gymCode, member_code: memberCode } = pass;
    const secretBytes = hexToBytes(pass.qr_secret_hex);

    async function tick() {
      const now = Math.floor(Date.now() / 1000);
      setSecondsLeft(WINDOW_SECONDS - (now % WINDOW_SECONDS));
      setPayload(await payloadFor(gymCode, memberCode, secretBytes, now));
    }

    tick();
    const interval = setInterval(tick, 1000);
    return () => clearInterval(interval);
  }, [pass]);

  if (!ready || !pass) return null;

  const dashoffset = RING_CIRCUMFERENCE * (1 - secondsLeft / WINDOW_SECONDS);

  return (
    <div className="flex flex-col items-center gap-4 text-center">
      <h1 className="text-2xl font-semibold">{t("passTitle")}</h1>
      <p className="text-sm opacity-70">{t("passSubtitle")}</p>
      <p className="font-medium">{pass.full_name}</p>

      {status && (
        <div className="w-full space-y-1 rounded border p-3 text-sm">
          <p className="font-medium">{status.plan_name}</p>
          <p className="opacity-70">
            {t("statusExpiry", { ad: status.expiry_date, bs: adIsoToBsLabel(status.expiry_date) })}
          </p>
          <p className="opacity-70">{t("statusDaysLeft", { count: status.days_left })}</p>
        </div>
      )}
      {!status && <p className="text-sm opacity-60">{t("statusNoMembership")}</p>}

      <p className="text-sm">{t("statusStreak", { count: streak })}</p>

      <p className="text-sm opacity-70">
        {nextClass
          ? t("statusNextClass", {
              name: nextClass.class_name,
              date: new Date(nextClass.starts_at).toLocaleString(),
            })
          : t("statusNoNextClass")}
      </p>

      <div className="relative flex items-center justify-center">
        {payload && <QRCodeSVG value={payload} size={QR_SIZE} data-testid="qr-payload" data-payload={payload} />}
        <svg
          className="absolute -m-3"
          width={QR_SIZE + 24}
          height={QR_SIZE + 24}
          viewBox="0 0 88 88"
        >
          <circle
            cx="44"
            cy="44"
            r={RING_RADIUS}
            fill="none"
            stroke="currentColor"
            strokeWidth="3"
            strokeOpacity="0.15"
          />
          <circle
            cx="44"
            cy="44"
            r={RING_RADIUS}
            fill="none"
            stroke="currentColor"
            strokeWidth="3"
            strokeDasharray={RING_CIRCUMFERENCE}
            strokeDashoffset={dashoffset}
            strokeLinecap="round"
            transform="rotate(-90 44 44)"
            className="transition-[stroke-dashoffset] duration-1000 ease-linear motion-reduce:transition-none"
          />
        </svg>
      </div>

      <p className="text-xs opacity-50">{secondsLeft}s</p>
      <p className="text-sm opacity-60">{pass.member_code}</p>

      <ReferralCard code={pass.member_code} />

      <Link
        href="/m/renew"
        className="mt-4 rounded bg-black px-4 py-2 text-sm text-white"
      >
        {t("renewCta")}
      </Link>

      <Link href="/m/coaching" className="text-sm underline opacity-70">
        {t("coachingLink")}
      </Link>

      <div className="flex flex-wrap items-center justify-center gap-3 text-sm">
        <Link href="/m/attendance" className="underline opacity-70">
          {t("attendanceTitle")}
        </Link>
        <Link href="/m/classes" className="underline opacity-70">
          {t("classesTitle")}
        </Link>
        <Link href="/m/invoices" className="underline opacity-70">
          {t("invoicesTitle")}
        </Link>
        <Link href="/m/freeze" className="underline opacity-70">
          {t("freezeTitle")}
        </Link>
        <Link href="/m/feedback" className="underline opacity-70">
          {t("feedbackTitle")}
        </Link>
      </div>

      {pushSupported() && pushState !== "enabled" && (
        <button
          onClick={async () => {
            const ok = await subscribeToPushNotifications(pass.token);
            setPushState(ok ? "enabled" : "error");
          }}
          className="text-sm underline opacity-70"
        >
          {t("enableNotifications")}
        </button>
      )}
      {pushState === "enabled" && (
        <p className="text-sm opacity-60">{t("notificationsEnabled")}</p>
      )}
      {pushState === "error" && <p className="text-sm text-red-600">{t("notificationsError")}</p>}
    </div>
  );
}
