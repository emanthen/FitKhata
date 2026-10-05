"use client";

import { useEffect, useState } from "react";
import { useTranslations } from "next-intl";
import { QRCodeSVG } from "qrcode.react";

import { hexToBytes, payloadFor } from "@/lib/qr";
import { getCachedPass, type CachedPass } from "@/lib/member/pass";

const WINDOW_SECONDS = 30;
const RING_RADIUS = 36;
const RING_CIRCUMFERENCE = 2 * Math.PI * RING_RADIUS;
const QR_SIZE = 220;

export default function MemberPassPage() {
  const t = useTranslations("member");
  const [pass, setPass] = useState<CachedPass | null>(null);
  const [ready, setReady] = useState(false);
  const [payload, setPayload] = useState<string | null>(null);
  const [secondsLeft, setSecondsLeft] = useState(WINDOW_SECONDS);

  useEffect(() => {
    setPass(getCachedPass());
    setReady(true);
  }, []);

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

  if (!ready) return null;
  if (!pass) return <p className="text-sm text-red-600">{t("passError")}</p>;

  const dashoffset = RING_CIRCUMFERENCE * (1 - secondsLeft / WINDOW_SECONDS);

  return (
    <div className="flex flex-col items-center gap-4 text-center">
      <h1 className="text-2xl font-semibold">{t("passTitle")}</h1>
      <p className="text-sm opacity-70">{t("passSubtitle")}</p>
      <p className="font-medium">{pass.full_name}</p>

      <div className="relative flex items-center justify-center">
        {payload && <QRCodeSVG value={payload} size={QR_SIZE} />}
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
    </div>
  );
}
