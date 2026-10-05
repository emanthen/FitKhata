"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { useTranslations } from "next-intl";
import { pairDevice } from "@fitkhata/api-client";
import { BrowserQRCodeReader } from "@zxing/browser";

import { hexToBytes, verify } from "@/lib/qr";
import { getDeviceAuth, setDeviceAuth, type DeviceAuth } from "@/lib/gate/auth";
import {
  enqueueCheckin,
  getMemberByCardUid,
  getMemberByCode,
  markLocalCheckin,
  type CachedMember,
} from "@/lib/gate/db";
import { classifyCheckin, type Classification } from "@/lib/gate/validate";
import { playCue } from "@/lib/gate/audio";
import { useGateSync } from "@/lib/gate/useGateSync";
import { syncOutbox } from "@/lib/gate/sync";

interface ScanResult {
  classification: Classification;
  member: CachedMember | null;
  reasonKey?: "reasonUnknownMember" | "reasonUnknownCard" | "reasonInvalidCode";
}

const RESULT_DISPLAY_MS = 4_000;

export default function GatePage() {
  const [auth, setAuth] = useState<DeviceAuth | null>(null);
  const [ready, setReady] = useState(false);

  useEffect(() => {
    setAuth(getDeviceAuth());
    setReady(true);
  }, []);

  if (!ready) return null;
  if (!auth) return <PairingScreen onPaired={setAuth} />;
  return <Kiosk />;
}

function PairingScreen({ onPaired }: { onPaired: (auth: DeviceAuth) => void }) {
  const t = useTranslations("gate");
  const [code, setCode] = useState("");
  const [deviceName, setDeviceName] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setLoading(true);
    try {
      const result = await pairDevice(code, deviceName);
      const auth: DeviceAuth = {
        device_id: result.device_id,
        gym_id: result.gym_id,
        token: result.token,
      };
      setDeviceAuth(auth);
      onPaired(auth);
    } catch {
      setError(t("pairError"));
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="w-full max-w-sm space-y-4 text-black">
      <h1 className="text-2xl font-semibold">{t("pairTitle")}</h1>
      {error && <p className="text-sm text-red-600">{error}</p>}
      <form onSubmit={submit} className="space-y-3">
        <input
          className="w-full rounded border px-3 py-2 text-center text-2xl tracking-widest"
          placeholder={t("pairCode")}
          value={code}
          onChange={(e) => setCode(e.target.value)}
          maxLength={6}
          minLength={6}
          required
        />
        <input
          className="w-full rounded border px-3 py-2"
          placeholder={t("pairDeviceName")}
          value={deviceName}
          onChange={(e) => setDeviceName(e.target.value)}
          required
        />
        <button
          type="submit"
          disabled={loading}
          className="w-full rounded bg-black px-3 py-2 text-white disabled:opacity-50"
        >
          {loading ? "..." : t("pairSubmit")}
        </button>
      </form>
    </div>
  );
}

function Kiosk() {
  const t = useTranslations("gate");
  const sync = useGateSync();
  const [result, setResult] = useState<ScanResult | null>(null);
  const videoRef = useRef<HTMLVideoElement>(null);
  const lockedRef = useRef(false);
  const lastPayloadRef = useRef<string | null>(null);

  const showResult = useCallback((r: ScanResult) => {
    if (lockedRef.current) return;
    lockedRef.current = true;
    setResult(r);
    playCue(r.classification);
    setTimeout(() => {
      setResult(null);
      lockedRef.current = false;
      lastPayloadRef.current = null;
    }, RESULT_DISPLAY_MS);
  }, []);

  const handleAccepted = useCallback(
    async (member: CachedMember, classification: Classification, source: "qr_gate" | "rfid") => {
      const nowIso = new Date().toISOString();
      await enqueueCheckin({
        client_uuid: crypto.randomUUID(),
        member_code: member.member_code,
        check_in_at: nowIso,
        source,
      });
      await markLocalCheckin(member.member_code, nowIso);
      showResult({ classification, member });
      syncOutbox().catch(() => {});
    },
    [showResult]
  );

  const handleQrPayload = useCallback(
    async (payload: string) => {
      if (lockedRef.current || payload === lastPayloadRef.current) return;
      const parts = payload.split(".");
      if (parts.length !== 3) return;
      const [, memberCode, token] = parts;
      lastPayloadRef.current = payload;

      const member = await getMemberByCode(memberCode);
      if (!member) {
        showResult({ classification: "red", member: null, reasonKey: "reasonUnknownMember" });
        return;
      }
      const now = new Date();
      const valid = await verify(
        hexToBytes(member.qr_secret_hex),
        token,
        Math.floor(now.getTime() / 1000)
      );
      if (!valid) {
        showResult({ classification: "red", member, reasonKey: "reasonInvalidCode" });
        return;
      }
      const classification = classifyCheckin(member, now);
      if (classification === "red") {
        showResult({ classification, member });
        return;
      }
      await handleAccepted(member, classification, "qr_gate");
    },
    [handleAccepted, showResult]
  );

  const handleCardUid = useCallback(
    async (cardUid: string) => {
      if (lockedRef.current) return;
      const member = await getMemberByCardUid(cardUid);
      if (!member) {
        showResult({ classification: "red", member: null, reasonKey: "reasonUnknownCard" });
        return;
      }
      const now = new Date();
      const classification = classifyCheckin(member, now);
      if (classification === "red") {
        showResult({ classification, member });
        return;
      }
      await handleAccepted(member, classification, "rfid");
    },
    [handleAccepted, showResult]
  );

  // Camera QR scanner — kept mounted for the component's whole lifetime
  // (see the JSX below, which hides it with opacity rather than
  // unmounting) so the decode loop never has to restart.
  useEffect(() => {
    if (!videoRef.current) return;
    const reader = new BrowserQRCodeReader();
    let controls: { stop: () => void } | undefined;
    reader
      .decodeFromVideoDevice(undefined, videoRef.current, (decodeResult) => {
        if (decodeResult) void handleQrPayload(decodeResult.getText());
      })
      .then((c) => {
        controls = c;
      })
      .catch(() => {
        // No camera available — HID/RFID input below still works.
      });
    return () => controls?.stop();
  }, [handleQrPayload]);

  // USB HID / RFID keyboard-wedge input: these readers emit a burst of
  // fast keystrokes terminated by Enter. A kiosk has no visible keyboard
  // to focus an <input> on, so this listens globally instead.
  useEffect(() => {
    let buffer = "";
    let lastKeyAt = 0;
    const MAX_GAP_MS = 50;

    function handleKeydown(e: KeyboardEvent) {
      const now = performance.now();
      if (now - lastKeyAt > MAX_GAP_MS) buffer = "";
      lastKeyAt = now;

      if (e.key === "Enter") {
        const scanned = buffer;
        buffer = "";
        if (scanned.length >= 4) void handleCardUid(scanned);
        return;
      }
      if (e.key.length === 1) buffer += e.key;
    }

    window.addEventListener("keydown", handleKeydown);
    return () => window.removeEventListener("keydown", handleKeydown);
  }, [handleCardUid]);

  const statusLabel = sync.syncError
    ? t("statusSyncError")
    : sync.online
      ? t("statusOnline")
      : t("statusOffline", { count: sync.pending });

  return (
    <div className="relative flex h-screen w-full flex-col items-center justify-center gap-6 bg-black text-white">
      <div
        className={`absolute right-4 top-4 rounded px-3 py-1 text-sm ${
          sync.syncError ? "bg-red-700" : sync.online ? "bg-green-700" : "bg-amber-700"
        }`}
      >
        {statusLabel}
      </div>

      <video
        ref={videoRef}
        muted
        className={`h-64 w-64 rounded bg-neutral-900 object-cover transition-opacity ${
          result ? "opacity-0" : "opacity-100"
        }`}
      />
      {!result && <p className="text-lg opacity-80">{t("scanPrompt")}</p>}

      {result && (
        <div className="absolute inset-0 flex items-center justify-center bg-black/90">
          <ResultBanner result={result} t={t} />
        </div>
      )}
    </div>
  );
}

function ResultBanner({ result, t }: { result: ScanResult; t: (key: string) => string }) {
  const bg =
    result.classification === "green"
      ? "bg-green-700"
      : result.classification === "amber"
        ? "bg-amber-700"
        : "bg-red-700";
  const label = result.reasonKey
    ? t(result.reasonKey)
    : result.classification === "green"
      ? t("resultGreen")
      : result.classification === "amber"
        ? t("resultAmber")
        : t("resultRed");

  return (
    <div className={`flex flex-col items-center gap-4 rounded-xl px-12 py-16 ${bg}`}>
      {result.member?.photo_url && (
        // eslint-disable-next-line @next/next/no-img-element -- remote, gym-uploaded photo, not a build-time asset
        <img src={result.member.photo_url} alt="" className="h-32 w-32 rounded-full object-cover" />
      )}
      <p className="text-3xl font-bold">{label}</p>
      {result.member && <p className="text-lg opacity-90">{result.member.member_code}</p>}
    </div>
  );
}
