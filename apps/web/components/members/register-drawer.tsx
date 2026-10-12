"use client";

import { useEffect, useRef, useState } from "react";
import { useTranslations } from "next-intl";
import { useQuery } from "@tanstack/react-query";
import {
  listMembers,
  listPlans,
  registerMember,
  sellMembership,
  uploadWaiver,
  type Member,
} from "@fitkhata/api-client";

import { adIsoToBsLabel } from "@/lib/bs-calendar";
import { formatNpr } from "@/lib/money";
import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import {
  Sheet,
  SheetContent,
  SheetDescription,
  SheetFooter,
  SheetHeader,
  SheetTitle,
} from "@/components/ui/sheet";

type Step = "form" | "sell" | "done";

export function RegisterDrawer({
  open,
  onOpenChange,
  onRegistered,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onRegistered: () => void;
}) {
  const t = useTranslations("admin");
  const [step, setStep] = useState<Step>("form");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [registeredMember, setRegisteredMember] = useState<Member | null>(null);

  const [phone, setPhone] = useState("");
  const [fullName, setFullName] = useState("");
  const [gender, setGender] = useState("");
  const [dob, setDob] = useState("");
  const [marketingOptIn, setMarketingOptIn] = useState(false);

  const existingMatch = useQuery({
    queryKey: ["members", "phone-check", phone],
    queryFn: () => listMembers({ q: phone }) as Promise<Member[]>,
    enabled: phone.trim().length >= 7,
  });
  const existingMember = existingMatch.data?.find((m) => m.phone === phone) ?? null;

  const photo = useWebcamCapture();
  const signature = useSignaturePad();

  function resetForm() {
    setStep("form");
    setError(null);
    setRegisteredMember(null);
    setPhone("");
    setFullName("");
    setGender("");
    setDob("");
    setMarketingOptIn(false);
    photo.reset();
    signature.clear();
  }

  async function submitRegistration(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setLoading(true);
    try {
      const member = await registerMember({
        full_name: fullName,
        phone,
        gender: gender || undefined,
        dob: dob || undefined,
        marketing_opt_in: marketingOptIn,
        photo: photo.blob ? new File([photo.blob], "photo.jpg", { type: "image/jpeg" }) : undefined,
      });
      if (signature.hasSignature) {
        const sigBlob = await signature.toBlob();
        if (sigBlob) await uploadWaiver(member.id, sigBlob);
      }
      setRegisteredMember(member);
      onRegistered();
      setStep("sell");
    } catch {
      setError(t("membersRegisterError"));
    } finally {
      setLoading(false);
    }
  }

  return (
    <Sheet open={open} onOpenChange={(next) => {
      onOpenChange(next);
      if (!next) resetForm();
    }}>
      <SheetContent className="w-full overflow-y-auto sm:max-w-lg">
        {step === "form" && (
          <>
            <SheetHeader>
              <SheetTitle>{t("membersRegisterDrawerTitle")}</SheetTitle>
              <SheetDescription>{t("membersRegisterDrawerDescription")}</SheetDescription>
            </SheetHeader>
            <form onSubmit={submitRegistration} className="space-y-4 px-4">
              {error && <p className="text-sm text-destructive">{error}</p>}

              <div className="space-y-1.5">
                <Label htmlFor="phone">{t("membersPhoneLabel")}</Label>
                <Input
                  id="phone"
                  placeholder="+977..."
                  value={phone}
                  onChange={(e) => setPhone(e.target.value)}
                  required
                />
                {existingMember && (
                  <p className="text-sm text-accent">
                    {t("membersAlreadyRegistered", {
                      name: existingMember.full_name,
                      code: existingMember.member_code,
                    })}
                  </p>
                )}
              </div>

              <div className="space-y-1.5">
                <Label htmlFor="full_name">{t("membersFullNameLabel")}</Label>
                <Input
                  id="full_name"
                  value={fullName}
                  onChange={(e) => setFullName(e.target.value)}
                  required
                />
              </div>

              <div className="space-y-1.5">
                <Label>{t("membersGenderLabel")}</Label>
                <Select value={gender} onValueChange={setGender}>
                  <SelectTrigger>
                    <SelectValue placeholder={t("membersGenderPlaceholder")} />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="male">{t("membersGenderMale")}</SelectItem>
                    <SelectItem value="female">{t("membersGenderFemale")}</SelectItem>
                    <SelectItem value="other">{t("membersGenderOther")}</SelectItem>
                  </SelectContent>
                </Select>
              </div>

              <div className="space-y-1.5">
                <Label htmlFor="dob">{t("membersDobLabel")}</Label>
                <Input
                  id="dob"
                  type="date"
                  value={dob}
                  onChange={(e) => setDob(e.target.value)}
                />
                {dob && (
                  <p className="text-xs opacity-60">{t("membersDobBsLabel", { bs: adIsoToBsLabel(dob) })}</p>
                )}
              </div>

              <label className="flex items-center gap-2 text-sm">
                <Checkbox
                  checked={marketingOptIn}
                  onCheckedChange={(checked) => setMarketingOptIn(checked === true)}
                />
                {t("membersMarketingOptIn")}
              </label>

              <div className="space-y-1.5">
                <Label>{t("membersPhotoLabel")}</Label>
                <WebcamCaptureView capture={photo} />
              </div>

              <div className="space-y-1.5">
                <Label>{t("membersWaiverSignatureLabel")}</Label>
                <SignaturePadView pad={signature} />
              </div>

              <SheetFooter className="px-0">
                <Button type="submit" disabled={loading || !!existingMember}>
                  {loading ? t("membersRegistering") : t("membersRegisterSubmitAction")}
                </Button>
              </SheetFooter>
            </form>
          </>
        )}

        {step === "sell" && registeredMember && (
          <SellStep
            member={registeredMember}
            onDone={() => setStep("done")}
            onSkip={() => setStep("done")}
          />
        )}

        {step === "done" && (
          <div className="space-y-4 p-4">
            <SheetHeader className="px-0">
              <SheetTitle>{t("membersDoneTitle")}</SheetTitle>
            </SheetHeader>
            <p className="text-sm">
              {t("membersRegisteredConfirmation", {
                name: registeredMember?.full_name ?? "",
                code: registeredMember?.member_code ?? "",
              })}
            </p>
            <div className="flex gap-2">
              <Button onClick={resetForm}>{t("membersRegisterAnother")}</Button>
              <Button variant="outline" onClick={() => onOpenChange(false)}>
                {t("membersCloseAction")}
              </Button>
            </div>
          </div>
        )}
      </SheetContent>
    </Sheet>
  );
}

function SellStep({
  member,
  onDone,
  onSkip,
}: {
  member: Member;
  onDone: () => void;
  onSkip: () => void;
}) {
  const t = useTranslations("admin");
  const [planId, setPlanId] = useState("");
  const [promoCode, setPromoCode] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const plans = useQuery({ queryKey: ["plans"], queryFn: listPlans });

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    if (!planId) return;
    setError(null);
    setLoading(true);
    try {
      await sellMembership(member.id, {
        plan_id: planId,
        promo_code: promoCode || undefined,
      });
      onDone();
    } catch {
      setError(t("membersSellError"));
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="space-y-4">
      <SheetHeader>
        <SheetTitle>{t("membersSellPlanTitle")}</SheetTitle>
        <SheetDescription>{member.full_name} ({member.member_code})</SheetDescription>
      </SheetHeader>
      <form onSubmit={submit} className="space-y-4 px-4">
        {error && <p className="text-sm text-red-600">{error}</p>}
        <div className="space-y-1.5">
          <Label>{t("membersPlanLabel")}</Label>
          <Select value={planId} onValueChange={setPlanId}>
            <SelectTrigger>
              <SelectValue placeholder={t("membersPlanPlaceholder")} />
            </SelectTrigger>
            <SelectContent>
              {(plans.data ?? []).map((p) => (
                <SelectItem key={p.id} value={p.id}>
                  {p.name} — {formatNpr(p.price_npr, { symbol: true })} ({p.duration_days}d)
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
        <div className="space-y-1.5">
          <Label htmlFor="promo">{t("membersPromoCodeLabel")}</Label>
          <Input id="promo" value={promoCode} onChange={(e) => setPromoCode(e.target.value)} />
        </div>
        <SheetFooter className="px-0">
          <Button type="submit" disabled={loading || !planId}>
            {loading ? t("membersSelling") : t("membersSellPlanAction")}
          </Button>
          <Button type="button" variant="outline" onClick={onSkip}>
            {t("membersSkipForNow")}
          </Button>
        </SheetFooter>
      </form>
    </div>
  );
}

// --- webcam capture ---------------------------------------------------

function useWebcamCapture() {
  const videoRef = useRef<HTMLVideoElement | null>(null);
  const [streaming, setStreaming] = useState(false);
  const [blob, setBlob] = useState<Blob | null>(null);
  const [previewUrl, setPreviewUrl] = useState<string | null>(null);

  async function start() {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ video: true });
      if (videoRef.current) {
        videoRef.current.srcObject = stream;
        await videoRef.current.play();
      }
      setStreaming(true);
    } catch {
      setStreaming(false);
    }
  }

  function stopStream() {
    const stream = videoRef.current?.srcObject as MediaStream | null;
    stream?.getTracks().forEach((t) => t.stop());
    setStreaming(false);
  }

  function capture() {
    const video = videoRef.current;
    if (!video) return;
    const canvas = document.createElement("canvas");
    canvas.width = video.videoWidth;
    canvas.height = video.videoHeight;
    canvas.getContext("2d")?.drawImage(video, 0, 0);
    canvas.toBlob((b) => {
      if (b) {
        setBlob(b);
        setPreviewUrl(URL.createObjectURL(b));
      }
    }, "image/jpeg");
    stopStream();
  }

  function reset() {
    stopStream();
    setBlob(null);
    setPreviewUrl(null);
  }

  useEffect(() => () => stopStream(), []);

  return { videoRef, streaming, blob, previewUrl, start, capture, reset };
}

function WebcamCaptureView({ capture }: { capture: ReturnType<typeof useWebcamCapture> }) {
  const t = useTranslations("admin");
  return (
    <div className="space-y-2">
      {capture.previewUrl ? (
        // eslint-disable-next-line @next/next/no-img-element
        <img src={capture.previewUrl} alt={t("membersCapturedPhotoAlt")} className="h-32 w-32 rounded object-cover" />
      ) : (
        <video ref={capture.videoRef} className="h-32 w-32 rounded bg-black object-cover" muted />
      )}
      <div className="flex gap-2">
        {!capture.streaming && !capture.previewUrl && (
          <Button type="button" variant="outline" size="sm" onClick={capture.start}>
            {t("membersStartCamera")}
          </Button>
        )}
        {capture.streaming && (
          <Button type="button" variant="outline" size="sm" onClick={capture.capture}>
            {t("membersCapture")}
          </Button>
        )}
        {capture.previewUrl && (
          <Button type="button" variant="outline" size="sm" onClick={capture.reset}>
            {t("membersRetake")}
          </Button>
        )}
      </div>
    </div>
  );
}

// --- signature pad ------------------------------------------------------

function useSignaturePad() {
  const canvasRef = useRef<HTMLCanvasElement | null>(null);
  const drawing = useRef(false);
  const [hasSignature, setHasSignature] = useState(false);

  function pos(e: React.PointerEvent<HTMLCanvasElement>) {
    const rect = e.currentTarget.getBoundingClientRect();
    return { x: e.clientX - rect.left, y: e.clientY - rect.top };
  }

  function onPointerDown(e: React.PointerEvent<HTMLCanvasElement>) {
    drawing.current = true;
    const ctx = canvasRef.current?.getContext("2d");
    const { x, y } = pos(e);
    ctx?.beginPath();
    ctx?.moveTo(x, y);
  }

  function onPointerMove(e: React.PointerEvent<HTMLCanvasElement>) {
    if (!drawing.current) return;
    const ctx = canvasRef.current?.getContext("2d");
    const { x, y } = pos(e);
    if (ctx) {
      ctx.lineTo(x, y);
      ctx.stroke();
    }
    setHasSignature(true);
  }

  function onPointerUp() {
    drawing.current = false;
  }

  function clear() {
    const canvas = canvasRef.current;
    canvas?.getContext("2d")?.clearRect(0, 0, canvas.width, canvas.height);
    setHasSignature(false);
  }

  function toBlob(): Promise<Blob | null> {
    return new Promise((resolve) => {
      if (canvasRef.current) {
        canvasRef.current.toBlob((b) => resolve(b), "image/png");
      } else {
        resolve(null);
      }
    });
  }

  return { canvasRef, onPointerDown, onPointerMove, onPointerUp, clear, hasSignature, toBlob };
}

function SignaturePadView({ pad }: { pad: ReturnType<typeof useSignaturePad> }) {
  const t = useTranslations("admin");
  return (
    <div className="space-y-2">
      <canvas
        ref={pad.canvasRef}
        width={320}
        height={120}
        className="touch-none rounded border bg-white"
        onPointerDown={pad.onPointerDown}
        onPointerMove={pad.onPointerMove}
        onPointerUp={pad.onPointerUp}
      />
      <Button type="button" variant="outline" size="sm" onClick={pad.clear}>
        {t("membersClearSignature")}
      </Button>
    </div>
  );
}
