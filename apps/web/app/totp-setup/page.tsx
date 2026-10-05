"use client";

import { useEffect, useState, type FormEvent } from "react";
import { useRouter } from "next/navigation";
import { QRCodeSVG } from "qrcode.react";
import { totpConfirm, totpSetup } from "@fitkhata/api-client";

import { redirectAfterAuth } from "@/lib/auth";

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
    <main className="mx-auto flex min-h-screen max-w-sm flex-col justify-center space-y-6 px-4">
      <div>
        <h1 className="text-2xl font-semibold">Set up two-factor authentication</h1>
        <p className="mt-2 text-sm opacity-70">
          Required for owners. Scan this with Google Authenticator, Authy, or similar — there&apos;s
          no way to skip this step.
        </p>
      </div>

      {otpauthUrl && (
        <div className="flex justify-center rounded border bg-white p-4">
          <QRCodeSVG value={otpauthUrl} size={200} />
        </div>
      )}
      {secret && (
        <p className="text-sm">
          Can&apos;t scan? Enter this code manually: <span className="font-mono">{secret}</span>
        </p>
      )}

      {error && <p className="text-sm text-red-600">{error}</p>}

      <form onSubmit={confirm} className="space-y-3">
        <input
          className="w-full rounded border px-3 py-2"
          placeholder="6-digit code from your app"
          value={code}
          onChange={(e) => setCode(e.target.value)}
          required
        />
        <button
          type="submit"
          disabled={loading}
          className="w-full rounded bg-black px-3 py-2 text-white disabled:opacity-50"
        >
          {loading ? "..." : "Confirm"}
        </button>
      </form>
    </main>
  );
}
