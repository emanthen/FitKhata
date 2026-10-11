"use client";

import { useState, type FormEvent } from "react";
import { useRouter } from "next/navigation";
import {
  createGym,
  createInvite,
  createOrganization,
  reissueTokens,
  tokenStore,
} from "@fitkhata/api-client";
import { TriangleAlert } from "lucide-react";

import { Logo } from "@/components/logo";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Checkbox } from "@/components/ui/checkbox";
import { Input } from "@/components/ui/input";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";

type Step = 1 | 2 | 3 | 4;

const STEP_LABELS = ["Organization", "First branch", "Plans", "Invite staff"] as const;

// Mandatory TOTP enrollment (see /totp-setup) is a full-page navigation away
// from this wizard, which would otherwise lose orgId/step and restart at
// step 1 — resubmitting step 1 would create a second organization for the
// same owner. Persisting progress (via tokenStore, session-scoped) is what
// makes resuming after that interrupt safe. tokenStore.clearOnboardingProgress()
// is called on every fresh login/register (see login/page.tsx's afterTokens)
// so a second identity on the same tab never inherits a stale orgId.
function loadProgress(): { step: Step; orgId: string | null } {
  return tokenStore.getOnboardingProgress() ?? { step: 1, orgId: null };
}

export default function OnboardingPage() {
  const router = useRouter();
  const initialProgress = useState(loadProgress)[0];
  const [step, setStep] = useState<Step>(initialProgress.step);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  const [orgName, setOrgName] = useState("");
  const [panVat, setPanVat] = useState("");
  const [vatRegistered, setVatRegistered] = useState(false);
  const [orgId, setOrgId] = useState<string | null>(initialProgress.orgId);

  const [gymCode, setGymCode] = useState("");
  const [gymName, setGymName] = useState("");
  const [city, setCity] = useState("");
  const [gymId, setGymId] = useState<string | null>(null);

  const [inviteRole, setInviteRole] = useState("front_desk");
  const [inviteLink, setInviteLink] = useState<string | null>(null);

  async function createOrgStep(e: FormEvent) {
    e.preventDefault();
    setError(null);
    setLoading(true);
    try {
      const org = await createOrganization({
        name: orgName,
        pan_vat_no: panVat,
        is_vat_registered: vatRegistered,
      });
      setOrgId(org.id);
      tokenStore.setOnboardingProgress({ step: 2, orgId: org.id });

      // Becoming an owner here changes this session's claims — reissue so
      // requires_totp_setup/role reflect it immediately rather than waiting
      // for the next login (see FR-1 acceptance: owner without 2FA must be
      // forced to enrol, not just next time they sign in).
      const tokens = await reissueTokens();
      tokenStore.setTokens(tokens.access, tokens.refresh);
      if (tokens.requires_totp_setup) {
        router.push("/totp-setup");
        return;
      }

      setStep(2);
    } catch {
      setError("Couldn't create the organization — check the details and try again.");
    } finally {
      setLoading(false);
    }
  }

  async function createGymStep(e: FormEvent) {
    e.preventDefault();
    if (!orgId) return;
    setError(null);
    setLoading(true);
    try {
      const gym = await createGym({ org: orgId, code: gymCode, name: gymName, city });
      setGymId(gym.id);
      tokenStore.setActiveGymId(gym.id);
      setStep(3);
      tokenStore.setOnboardingProgress({ step: 3, orgId });
    } catch {
      setError("Couldn't create the branch — the code may already be taken.");
    } finally {
      setLoading(false);
    }
  }

  async function sendInvite(e: FormEvent) {
    e.preventDefault();
    if (!gymId) return;
    setError(null);
    setLoading(true);
    try {
      const { token } = await createInvite(inviteRole, gymId);
      setInviteLink(`${window.location.origin}/invite/${token}`);
    } catch {
      setError("Couldn't create the invite link.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <main className="font-dashboard mx-auto max-w-lg space-y-6 px-4 py-12">
      <Logo size={26} />

      <ol className="flex gap-1.5">
        {STEP_LABELS.map((label, i) => {
          const n = (i + 1) as Step;
          return (
            <li
              key={label}
              className={`flex-1 rounded-md px-2 py-1.5 text-center text-xs font-medium transition-colors ${
                step === n
                  ? "bg-primary text-primary-foreground"
                  : step > n
                    ? "bg-primary/10 text-primary"
                    : "bg-muted text-muted-foreground"
              }`}
            >
              {n}. {label}
            </li>
          );
        })}
      </ol>

      {error && (
        <p className="flex items-center gap-1.5 text-sm text-destructive">
          <TriangleAlert size={14} strokeWidth={2} />
          {error}
        </p>
      )}

      {step === 1 && (
        <Card>
          <CardContent>
            <form onSubmit={createOrgStep} className="space-y-3">
              <h2 className="text-lg font-semibold tracking-tight">Your organization</h2>
              <Input
                placeholder="Organization name"
                value={orgName}
                onChange={(e) => setOrgName(e.target.value)}
                className="h-11"
                required
              />
              <Input
                placeholder="PAN/VAT number"
                value={panVat}
                onChange={(e) => setPanVat(e.target.value)}
                className="h-11"
              />
              <label className="flex items-center gap-2 text-sm">
                <Checkbox
                  checked={vatRegistered}
                  onCheckedChange={(checked) => setVatRegistered(checked === true)}
                />
                VAT registered
              </label>
              <Button type="submit" disabled={loading}>
                {loading ? "..." : "Next"}
              </Button>
            </form>
          </CardContent>
        </Card>
      )}

      {step === 2 && (
        <Card>
          <CardContent>
            <form onSubmit={createGymStep} className="space-y-3">
              <h2 className="text-lg font-semibold tracking-tight">Your first branch</h2>
              <Input
                placeholder="Branch code (e.g. KTM1)"
                value={gymCode}
                onChange={(e) => setGymCode(e.target.value)}
                className="h-11"
                required
              />
              <Input
                placeholder="Branch name"
                value={gymName}
                onChange={(e) => setGymName(e.target.value)}
                className="h-11"
                required
              />
              <Input
                placeholder="City"
                value={city}
                onChange={(e) => setCity(e.target.value)}
                className="h-11"
              />
              <Button type="submit" disabled={loading}>
                {loading ? "..." : "Next"}
              </Button>
            </form>
          </CardContent>
        </Card>
      )}

      {step === 3 && (
        <Card>
          <CardContent className="space-y-3">
            <h2 className="text-lg font-semibold tracking-tight">Membership plans</h2>
            <p className="text-sm text-muted-foreground">
              We&apos;ll set up default membership plans for you here - this comes with billing, in
              a later release. You can skip this for now and add plans afterward.
            </p>
            <Button
              type="button"
              onClick={() => {
                setStep(4);
                tokenStore.setOnboardingProgress({ step: 4, orgId });
              }}
            >
              Next
            </Button>
          </CardContent>
        </Card>
      )}

      {step === 4 && (
        <Card>
          <CardContent className="space-y-4">
            <h2 className="text-lg font-semibold tracking-tight">Invite your team</h2>
            <form onSubmit={sendInvite} className="flex gap-2">
              <Select value={inviteRole} onValueChange={setInviteRole}>
                <SelectTrigger className="h-9 flex-1">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="manager">Manager</SelectItem>
                  <SelectItem value="front_desk">Front desk</SelectItem>
                  <SelectItem value="trainer">Trainer</SelectItem>
                </SelectContent>
              </Select>
              <Button type="submit" disabled={loading}>
                {loading ? "..." : "Create invite link"}
              </Button>
            </form>
            {inviteLink && (
              <p className="font-dashboard-mono break-all rounded-lg border bg-muted/40 p-3 text-xs">
                {inviteLink}
                <br />
                <span className="font-sans text-muted-foreground">
                  Valid for 72 hours. Share it with the new staff member.
                </span>
              </p>
            )}
            <Button
              type="button"
              variant="outline"
              onClick={() => {
                tokenStore.clearOnboardingProgress();
                if (gymId) router.push(`/${gymId}`);
              }}
            >
              Done - go to dashboard
            </Button>
          </CardContent>
        </Card>
      )}
    </main>
  );
}
