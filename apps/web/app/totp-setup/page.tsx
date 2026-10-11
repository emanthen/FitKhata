"use client";

import { useEffect, useState, type FormEvent } from "react";
import { useRouter } from "next/navigation";
import { QRCodeSVG } from "qrcode.react";
import { totpConfirm, totpSetup } from "@fitkhata/api-client";
import { ShieldCheck, TriangleAlert } from "lucide-react";

import { redirectAfterAuth } from "@/lib/auth";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Input } from "@/components/ui/input";

export default function TotpSetupPage() {
  const router = useRouter();
  const [secret, setSecret] = useState<string | null>(null);
  const [otpauthUrl, setOtpauthUrl] = useState<string | null>(null);
  const [code, setCode] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    totpSetup().then((res: { secret: string; otpauth_url: string }) => {
      setSecret(res.secret);
      setOtpauthUrl(res.otpauth_url);
    });
  }, []);

  async function confirm(e: FormEvent) {
    e.preventDefault();
    setError(null);
    setLoading(true);
    try {
      await totpConfirm(code);
      await redirectAfterAuth((path) => router.push(path));
    } catch {
      setError("Incorrect code — try again.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <main className="font-dashboard mx-auto flex min-h-screen max-w-sm flex-col justify-center space-y-6 px-4">
      <div>
        <h1 className="flex items-center gap-2 text-xl font-semibold tracking-tight">
          <ShieldCheck size={18} strokeWidth={2} className="text-primary" />
          Set up two-factor authentication
        </h1>
        <p className="mt-2 text-sm text-muted-foreground">
          Required for owners. Scan this with Google Authenticator, Authy, or similar - there&apos;s
          no way to skip this step.
        </p>
      </div>

      {otpauthUrl && (
        <Card>
          <CardContent className="flex justify-center bg-white py-6">
            <QRCodeSVG value={otpauthUrl} size={200} />
          </CardContent>
        </Card>
      )}
      {secret && (
        <p className="text-sm">
          Can&apos;t scan? Enter this code manually:{" "}
          <span className="font-dashboard-mono">{secret}</span>
        </p>
      )}

      {error && (
        <p className="flex items-center gap-1.5 text-sm text-destructive">
          <TriangleAlert size={14} strokeWidth={2} />
          {error}
        </p>
      )}

      <form onSubmit={confirm} className="space-y-3">
        <Input
          placeholder="6-digit code from your app"
          value={code}
          onChange={(e) => setCode(e.target.value)}
          className="font-dashboard-mono h-11"
          required
        />
        <Button type="submit" disabled={loading} size="lg" className="h-11 w-full">
          {loading ? "..." : "Confirm"}
        </Button>
      </form>
    </main>
  );
}
