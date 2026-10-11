"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { useTranslations } from "next-intl";
import { login, otpSend, otpVerify, tokenStore } from "@fitkhata/api-client";
import { TriangleAlert } from "lucide-react";

import { redirectAfterAuth } from "@/lib/auth";
import { Logo } from "@/components/logo";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";

type Tab = "password" | "otp";

export default function LoginPage() {
  const t = useTranslations("auth");
  const router = useRouter();
  const [tab, setTab] = useState<Tab>("password");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  async function afterTokens(requiresTotpSetup: boolean) {
    // A fresh login/register on this tab — any onboarding progress in
    // sessionStorage belongs to whoever was last signed in here, not this
    // identity. Must NOT live in redirectAfterAuth: that's also called from
    // totp-setup after the onboarding wizard's own mid-flow interrupt,
    // where clearing would destroy the very progress being resumed.
    tokenStore.clearOnboardingProgress();
    if (requiresTotpSetup) {
      router.push("/totp-setup");
      return;
    }
    await redirectAfterAuth((path) => router.push(path));
  }

  return (
    <div className="w-full space-y-6">
      <div className="flex flex-col items-center gap-4">
        <Logo size={28} />
        <h1 className="text-xl font-semibold tracking-tight">{t("signIn")}</h1>
      </div>

      <Tabs value={tab} onValueChange={(v) => setTab(v as Tab)}>
        <TabsList variant="line" className="w-full">
          <TabsTrigger value="password">Password</TabsTrigger>
          <TabsTrigger value="otp">OTP</TabsTrigger>
        </TabsList>

        {error && (
          <p className="flex items-center gap-1.5 text-sm text-destructive">
            <TriangleAlert size={14} strokeWidth={2} />
            {error}
          </p>
        )}

        <TabsContent value="password">
          <PasswordForm
            loading={loading}
            setLoading={setLoading}
            setError={setError}
            onSuccess={afterTokens}
          />
        </TabsContent>
        <TabsContent value="otp">
          <OtpForm loading={loading} setLoading={setLoading} setError={setError} onSuccess={afterTokens} />
        </TabsContent>
      </Tabs>
    </div>
  );
}

function PasswordForm({
  loading,
  setLoading,
  setError,
  onSuccess,
}: {
  loading: boolean;
  setLoading: (v: boolean) => void;
  setError: (v: string | null) => void;
  onSuccess: (requiresTotpSetup: boolean) => void;
}) {
  const [identifier, setIdentifier] = useState("");
  const [password, setPassword] = useState("");
  const [needsTotp, setNeedsTotp] = useState(false);
  const [totpCode, setTotpCode] = useState("");

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setLoading(true);
    try {
      const tokens = await login(identifier, password, needsTotp ? totpCode : undefined);
      tokenStore.setTokens(tokens.access, tokens.refresh);
      onSuccess(tokens.requires_totp_setup);
    } catch (err: unknown) {
      const detail = getErrorDetail(err);
      if (detail === "totp_required") {
        setNeedsTotp(true);
      } else {
        setError(detail ?? "Invalid credentials.");
      }
    } finally {
      setLoading(false);
    }
  }

  return (
    <form onSubmit={submit} className="space-y-3 pt-4">
      <Input
        placeholder="Phone or email"
        value={identifier}
        onChange={(e) => setIdentifier(e.target.value)}
        className="h-11"
        required
      />
      <Input
        type="password"
        placeholder="Password"
        value={password}
        onChange={(e) => setPassword(e.target.value)}
        className="h-11"
        required
      />
      {needsTotp && (
        <Input
          placeholder="6-digit authenticator code"
          value={totpCode}
          onChange={(e) => setTotpCode(e.target.value)}
          className="font-dashboard-mono h-11"
          required
        />
      )}
      <Button type="submit" disabled={loading} size="lg" className="h-11 w-full">
        {loading ? "..." : "Sign in"}
      </Button>
    </form>
  );
}

function OtpForm({
  loading,
  setLoading,
  setError,
  onSuccess,
}: {
  loading: boolean;
  setLoading: (v: boolean) => void;
  setError: (v: string | null) => void;
  onSuccess: (requiresTotpSetup: boolean) => void;
}) {
  const [phone, setPhone] = useState("");
  const [code, setCode] = useState("");
  const [sent, setSent] = useState(false);
  const [registrationToken, setRegistrationToken] = useState<string | null>(null);
  const [fullName, setFullName] = useState("");
  const [password, setPassword] = useState("");

  async function sendCode(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setLoading(true);
    try {
      await otpSend(phone);
      setSent(true);
    } catch (err: unknown) {
      setError(getErrorDetail(err) ?? "Couldn't send the code.");
    } finally {
      setLoading(false);
    }
  }

  async function verifyCode(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setLoading(true);
    try {
      const result = await otpVerify(phone, code);
      if (!result.user_exists) {
        setRegistrationToken(result.registration_token!);
        return;
      }
      tokenStore.setTokens(result.access!, result.refresh!);
      onSuccess(!!result.requires_totp_setup);
    } catch (err: unknown) {
      setError(getErrorDetail(err) ?? "Incorrect code.");
    } finally {
      setLoading(false);
    }
  }

  async function completeRegistration(e: React.FormEvent) {
    e.preventDefault();
    if (!registrationToken) return;
    setError(null);
    setLoading(true);
    try {
      const { register } = await import("@fitkhata/api-client");
      const tokens = await register(registrationToken, fullName, password);
      tokenStore.setTokens(tokens.access, tokens.refresh);
      onSuccess(tokens.requires_totp_setup);
    } catch (err: unknown) {
      setError(getErrorDetail(err) ?? "Couldn't create your account.");
    } finally {
      setLoading(false);
    }
  }

  if (registrationToken) {
    return (
      <form onSubmit={completeRegistration} className="space-y-3 pt-4">
        <p className="text-sm text-muted-foreground">No account yet for {phone} - let&apos;s create one.</p>
        <Input
          placeholder="Full name"
          value={fullName}
          onChange={(e) => setFullName(e.target.value)}
          className="h-11"
          required
        />
        <Input
          type="password"
          placeholder="Choose a password"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          className="h-11"
          minLength={8}
          required
        />
        <Button type="submit" disabled={loading} size="lg" className="h-11 w-full">
          {loading ? "..." : "Create account"}
        </Button>
      </form>
    );
  }

  if (!sent) {
    return (
      <form onSubmit={sendCode} className="space-y-3 pt-4">
        <Input
          placeholder="+977..."
          value={phone}
          onChange={(e) => setPhone(e.target.value)}
          className="h-11"
          required
        />
        <Button type="submit" disabled={loading} size="lg" className="h-11 w-full">
          {loading ? "..." : "Send code"}
        </Button>
      </form>
    );
  }

  return (
    <form onSubmit={verifyCode} className="space-y-3 pt-4">
      <p className="text-sm text-muted-foreground">Code sent to {phone}.</p>
      <Input
        placeholder="6-digit code"
        value={code}
        onChange={(e) => setCode(e.target.value)}
        className="font-dashboard-mono h-11"
        required
      />
      <Button type="submit" disabled={loading} size="lg" className="h-11 w-full">
        {loading ? "..." : "Verify"}
      </Button>
    </form>
  );
}

function getErrorDetail(err: unknown): string | null {
  if (typeof err === "object" && err !== null && "response" in err) {
    const response = (err as { response?: { data?: { detail?: string } } }).response;
    return response?.data?.detail ?? null;
  }
  return null;
}
