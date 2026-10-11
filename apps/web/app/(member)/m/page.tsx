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
import {
  Bell,
  CalendarClock,
  CalendarDays,
  Dumbbell,
  Flame,
  MessageSquareText,
  Receipt,
  Snowflake,
  Wallet,
} from "lucide-react";

import { hexToBytes, payloadFor } from "@/lib/qr";
import { getCachedPass, type CachedPass } from "@/lib/member/pass";
import { pushSupported, subscribeToPushNotifications } from "@/lib/push";
import { adIsoToBsLabel } from "@/lib/bs-calendar";
import { ReferralCard } from "@/components/member/referral-card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";

const WINDOW_SECONDS = 30;
const RING_RADIUS = 36;
const RING_CIRCUMFERENCE = 2 * Math.PI * RING_RADIUS;
const QR_SIZE = 220;

const QUICK_ACTIONS = [
  { href: "/m/attendance", icon: CalendarDays, key: "attendanceTitle" as const },
  { href: "/m/classes", icon: CalendarClock, key: "classesTitle" as const },
  { href: "/m/invoices", icon: Receipt, key: "invoicesTitle" as const },
  { href: "/m/freeze", icon: Snowflake, key: "freezeTitle" as const },
  { href: "/m/feedback", icon: MessageSquareText, key: "feedbackTitle" as const },
  { href: "/m/coaching", icon: Dumbbell, key: "coachingLink" as const },
];

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
  const lowDays = status ? status.days_left <= 3 : false;

  return (
    <div className="flex flex-col items-center gap-5 text-center">
      <div>
        <h1 className="text-xl font-semibold tracking-tight">{t("passTitle")}</h1>
        <p className="mt-1 text-sm text-muted-foreground">{t("passSubtitle")}</p>
      </div>

      <p className="font-medium">{pass.full_name}</p>

      {status ? (
        <Card className="w-full">
          <CardContent className="space-y-1.5 text-left">
            <div className="flex items-center justify-between">
              <p className="font-medium">{status.plan_name}</p>
              <Badge variant={lowDays ? "destructive" : "secondary"}>
                {t("statusDaysLeft", { count: status.days_left })}
              </Badge>
            </div>
            <p className="font-dashboard-mono text-sm text-muted-foreground">
              {t("statusExpiry", { ad: status.expiry_date, bs: adIsoToBsLabel(status.expiry_date) })}
            </p>
          </CardContent>
        </Card>
      ) : (
        <p className="text-sm text-muted-foreground">{t("statusNoMembership")}</p>
      )}

      <div className="flex w-full gap-3">
        <div className="flex flex-1 items-center gap-2 rounded-xl border bg-card px-3 py-2.5 text-left">
          <Flame size={16} strokeWidth={2} className="shrink-0 text-accent" />
          <span className="text-sm">{t("statusStreak", { count: streak })}</span>
        </div>
        <div className="flex flex-1 items-center gap-2 rounded-xl border bg-card px-3 py-2.5 text-left">
          <CalendarClock size={16} strokeWidth={2} className="shrink-0 text-primary" />
          <span className="text-xs leading-tight">
            {nextClass
              ? t("statusNextClass", {
                  name: nextClass.class_name,
                  date: new Date(nextClass.starts_at).toLocaleString(),
                })
              : t("statusNoNextClass")}
          </span>
        </div>
      </div>

      <Card className="w-full">
        <CardContent className="flex flex-col items-center gap-3">
          <div className="relative flex items-center justify-center text-primary">
            {payload && (
              <QRCodeSVG value={payload} size={QR_SIZE} data-testid="qr-payload" data-payload={payload} />
            )}
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
          <p className="font-dashboard-mono text-xs text-muted-foreground">{secondsLeft}s</p>
          <p className="font-dashboard-mono text-sm font-medium tracking-wide">{pass.member_code}</p>
        </CardContent>
      </Card>

      <ReferralCard code={pass.member_code} />

      <Button size="lg" className="h-12 w-full text-base" asChild>
        <Link href="/m/renew">
          <Wallet size={17} strokeWidth={2} data-icon="inline-start" />
          {t("renewCta")}
        </Link>
      </Button>

      <div className="grid w-full grid-cols-3 gap-2.5">
        {QUICK_ACTIONS.map((action) => {
          const Icon = action.icon;
          return (
            <Link
              key={action.href}
              href={action.href}
              className="flex flex-col items-center gap-1.5 rounded-xl border bg-card px-2 py-3.5 text-center transition-colors hover:bg-muted/60"
            >
              <Icon size={19} strokeWidth={1.75} className="text-primary" />
              <span className="text-xs leading-tight text-foreground/80">{t(action.key)}</span>
            </Link>
          );
        })}
      </div>

      {pushSupported() && pushState !== "enabled" && (
        <Button
          variant="ghost"
          size="sm"
          className="text-muted-foreground"
          onClick={async () => {
            const ok = await subscribeToPushNotifications(pass.token);
            setPushState(ok ? "enabled" : "error");
          }}
        >
          <Bell size={14} strokeWidth={2} data-icon="inline-start" />
          {t("enableNotifications")}
        </Button>
      )}
      {pushState === "enabled" && (
        <p className="text-sm text-muted-foreground">{t("notificationsEnabled")}</p>
      )}
      {pushState === "error" && <p className="text-sm text-destructive">{t("notificationsError")}</p>}
    </div>
  );
}
