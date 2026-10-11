"use client";

import { useState, type FormEvent } from "react";
import { useParams, useRouter } from "next/navigation";
import { acceptInvite, tokenStore } from "@fitkhata/api-client";
import { TriangleAlert, UserPlus } from "lucide-react";

import { redirectAfterAuth } from "@/lib/auth";
import { Logo } from "@/components/logo";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";

export default function AcceptInvitePage() {
  const { token } = useParams<{ token: string }>();
  const router = useRouter();
  const [phone, setPhone] = useState("");
  const [fullName, setFullName] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  async function submit(e: FormEvent) {
    e.preventDefault();
    setError(null);
    setLoading(true);
    try {
      const tokens = await acceptInvite(token, phone, fullName, password);
      tokenStore.setTokens(tokens.access, tokens.refresh);
      await redirectAfterAuth((path) => router.push(path));
    } catch {
      setError("This invite link is invalid or has expired.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <main className="font-dashboard mx-auto flex min-h-screen max-w-sm flex-col justify-center space-y-6 px-4">
      <div className="flex flex-col items-center gap-4 text-center">
        <Logo size={28} />
        <div>
          <h1 className="flex items-center justify-center gap-2 text-xl font-semibold tracking-tight">
            <UserPlus size={18} strokeWidth={2} className="text-primary" />
            Join your team
          </h1>
          <p className="mt-1 text-sm text-muted-foreground">Set up your account to accept the invite.</p>
        </div>
      </div>

      {error && (
        <p className="flex items-center gap-1.5 text-sm text-destructive">
          <TriangleAlert size={14} strokeWidth={2} />
          {error}
        </p>
      )}

      <form onSubmit={submit} className="space-y-3">
        <Input
          placeholder="+977..."
          value={phone}
          onChange={(e) => setPhone(e.target.value)}
          className="h-11"
          required
        />
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
          {loading ? "..." : "Join"}
        </Button>
      </form>
    </main>
  );
}
