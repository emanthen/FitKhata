"use client";

import { useState, type FormEvent } from "react";
import { useRouter } from "next/navigation";
import {
  createGym,
  createInvite,
  createOrganization,
  createPlan,
  reissueTokens,
  tokenStore,
} from "@fitkhata/api-client";
import {
  ArrowRight,
  Building2,
  Check,
  LayoutDashboard,
  MapPin,
  Send,
  Ticket,
  TriangleAlert,
  UserPlus,
} from "lucide-react";

import { Logo } from "@/components/logo";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader } from "@/components/ui/card";
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

const STEPS = [
  {
    label: "Organization",
    description: "Your billing account and legal details.",
    icon: Building2,
  },
  {
    label: "First branch",
    description: "The location members and staff will check in to.",
    icon: MapPin,
  },
  {
    label: "Plans",
    description: "What you charge, for how long.",
    icon: Ticket,
  },
  {
    label: "Invite staff",
    description: "Get your team logged in.",
    icon: UserPlus,
  },
] as const;

const PLAN_TEMPLATES = [
  { key: "monthly", name: "Monthly", durationDays: 30 },
  { key: "quarterly", name: "3 Months", durationDays: 90 },
  { key: "annual", name: "12 Months", durationDays: 365 },
] as const;

type PlanSelection = { checked: boolean; price: string };

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
  const [address, setAddress] = useState("");
  const [city, setCity] = useState("");
  const [phone, setPhone] = useState("");
  const [gymId, setGymId] = useState<string | null>(null);

  const [planSelections, setPlanSelections] = useState<Record<string, PlanSelection>>(
    Object.fromEntries(
      PLAN_TEMPLATES.map((p) => [p.key, { checked: p.key === "monthly", price: "" }])
    )
  );

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
      const gym = await createGym({ org: orgId, code: gymCode, name: gymName, address, city, phone });
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

  function updatePlanSelection(key: string, patch: Partial<PlanSelection>) {
    setPlanSelections((prev) => ({ ...prev, [key]: { ...prev[key], ...patch } }));
  }

  async function createPlansStep(e: FormEvent) {
    e.preventDefault();
    setError(null);
    const toCreate = PLAN_TEMPLATES.filter(
      (p) => planSelections[p.key].checked && planSelections[p.key].price.trim()
    );
    if (toCreate.length === 0) {
      setStep(4);
      tokenStore.setOnboardingProgress({ step: 4, orgId });
      return;
    }
    setLoading(true);
    try {
      for (const plan of toCreate) {
        await createPlan({
          name: plan.name,
          duration_days: plan.durationDays,
          price_npr: planSelections[plan.key].price,
          joining_fee_npr: "0",
          access_hours: {},
          pt_sessions: 0,
          max_freeze_days: 0,
          is_active: true,
        });
      }
      setStep(4);
      tokenStore.setOnboardingProgress({ step: 4, orgId });
    } catch {
      setError("Couldn't create one of those plans — check the prices and try again.");
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
    <div className="font-dashboard grid min-h-screen lg:grid-cols-[360px_1fr]">
      <aside className="hidden flex-col justify-between bg-primary p-10 text-primary-foreground lg:flex">
        <div>
          <div className="text-white">
            <Logo size={26} />
          </div>
          <ol className="mt-12 space-y-7">
            {STEPS.map((s, i) => {
              const n = (i + 1) as Step;
              const Icon = s.icon;
              const done = step > n;
              const current = step === n;
              return (
                <li key={s.label} className="flex items-start gap-3">
                  <span
                    className={`flex size-8 shrink-0 items-center justify-center rounded-full border transition-colors ${
                      current
                        ? "border-white bg-white text-primary"
                        : done
                          ? "border-white/40 bg-white/15 text-white"
                          : "border-white/25 text-white/50"
                    }`}
                  >
                    {done ? <Check size={15} strokeWidth={2.5} /> : <Icon size={15} strokeWidth={2} />}
                  </span>
                  <div className={current ? "text-white" : done ? "text-white/80" : "text-white/45"}>
                    <p className="text-sm font-medium">{s.label}</p>
                    <p className="mt-0.5 text-xs leading-relaxed">{s.description}</p>
                  </div>
                </li>
              );
            })}
          </ol>
        </div>
      </aside>

      <main className="mx-auto flex w-full max-w-xl flex-col justify-center gap-6 px-4 py-12 lg:px-16">
        <div className="lg:hidden">
          <Logo size={26} />
        </div>

        {(() => {
          const s = STEPS[step - 1];
          const Icon = s.icon;
          return (
            <div className="flex items-center gap-3.5">
              <span className="flex size-11 shrink-0 items-center justify-center rounded-xl bg-primary/10 text-primary">
                <Icon size={20} strokeWidth={2} />
              </span>
              <div>
                <p className="font-dashboard-mono text-xs text-muted-foreground">
                  Step {step} of {STEPS.length}
                </p>
                <h1 className="text-xl font-semibold tracking-tight">{s.label}</h1>
              </div>
            </div>
          );
        })()}

        {error && (
          <p className="flex items-center gap-1.5 text-sm text-destructive">
            <TriangleAlert size={14} strokeWidth={2} />
            {error}
          </p>
        )}

        {step === 1 && (
        <Card>
          <CardHeader>
            <p className="text-sm text-muted-foreground">
              One organization can run several branches under the same billing account.
            </p>
          </CardHeader>
          <CardContent>
            <form onSubmit={createOrgStep} className="space-y-3">
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
              <Button type="submit" disabled={loading} size="lg" className="h-11 w-full gap-1.5">
                {loading ? "..." : (
                  <>
                    Next
                    <ArrowRight size={16} strokeWidth={2} />
                  </>
                )}
              </Button>
            </form>
          </CardContent>
        </Card>
      )}

      {step === 2 && (
        <Card>
          <CardHeader>
            <p className="text-sm text-muted-foreground">
              This is what members and staff will see as their gym location.
            </p>
          </CardHeader>
          <CardContent>
            <form onSubmit={createGymStep} className="space-y-3">
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
                placeholder="Street address"
                value={address}
                onChange={(e) => setAddress(e.target.value)}
                className="h-11"
              />
              <div className="flex gap-3">
                <Input
                  placeholder="City"
                  value={city}
                  onChange={(e) => setCity(e.target.value)}
                  className="h-11"
                />
                <Input
                  type="tel"
                  placeholder="Branch phone"
                  value={phone}
                  onChange={(e) => setPhone(e.target.value)}
                  className="h-11"
                />
              </div>
              <Button type="submit" disabled={loading} size="lg" className="h-11 w-full gap-1.5">
                {loading ? "..." : (
                  <>
                    Next
                    <ArrowRight size={16} strokeWidth={2} />
                  </>
                )}
              </Button>
            </form>
          </CardContent>
        </Card>
      )}

      {step === 3 && (
        <Card>
          <CardHeader>
            <p className="text-sm text-muted-foreground">
              Set a price for the durations you sell. Leave a price blank to skip it - you can
              always add more plans later from Settings.
            </p>
          </CardHeader>
          <CardContent>
            <form onSubmit={createPlansStep} className="space-y-4">
              <div className="space-y-2">
                {PLAN_TEMPLATES.map((plan) => {
                  const selection = planSelections[plan.key];
                  return (
                    <div
                      key={plan.key}
                      className="flex items-center gap-3 rounded-lg border px-3 py-2.5"
                    >
                      <Checkbox
                        checked={selection.checked}
                        onCheckedChange={(checked) =>
                          updatePlanSelection(plan.key, { checked: checked === true })
                        }
                      />
                      <span className="w-24 shrink-0 text-sm">{plan.name}</span>
                      <div className="flex flex-1 items-center gap-1.5">
                        <span className="text-sm text-muted-foreground">Rs</span>
                        <Input
                          type="number"
                          step="0.01"
                          placeholder="Price"
                          value={selection.price}
                          onChange={(e) => updatePlanSelection(plan.key, { price: e.target.value })}
                          disabled={!selection.checked}
                          className="h-9"
                        />
                      </div>
                    </div>
                  );
                })}
              </div>

              <Button type="submit" disabled={loading} size="lg" className="h-11 w-full gap-1.5">
                {loading ? "..." : (
                  <>
                    Next
                    <ArrowRight size={16} strokeWidth={2} />
                  </>
                )}
              </Button>
            </form>
          </CardContent>
        </Card>
      )}

      {step === 4 && (
        <Card>
          <CardHeader>
            <p className="text-sm text-muted-foreground">
              Generates a one-time link that sets up their login - send it however you like.
            </p>
          </CardHeader>
          <CardContent className="space-y-4">
            <form onSubmit={sendInvite} className="flex gap-2">
              <Select value={inviteRole} onValueChange={setInviteRole}>
                <SelectTrigger className="h-11 flex-1">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="manager">Manager</SelectItem>
                  <SelectItem value="front_desk">Front desk</SelectItem>
                  <SelectItem value="trainer">Trainer</SelectItem>
                </SelectContent>
              </Select>
              <Button type="submit" disabled={loading} size="lg" className="h-11 shrink-0 gap-1.5">
                {loading ? "..." : (
                  <>
                    <Send size={15} strokeWidth={2} />
                    Create link
                  </>
                )}
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
              size="lg"
              className="h-11 w-full gap-1.5"
              onClick={() => {
                tokenStore.clearOnboardingProgress();
                if (gymId) router.push(`/${gymId}`);
              }}
            >
              <LayoutDashboard size={16} strokeWidth={2} />
              Done - go to dashboard
            </Button>
          </CardContent>
        </Card>
      )}
      </main>
    </div>
  );
}
