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

type Step = 1 | 2 | 3 | 4;

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
    <main className="mx-auto max-w-lg space-y-6 px-4 py-12">
      <ol className="flex gap-2 text-sm">
        {(["Organization", "First branch", "Plans", "Invite staff"] as const).map((label, i) => (
          <li
            key={label}
            className={`rounded px-2 py-1 ${step === i + 1 ? "bg-black text-white" : "opacity-50"}`}
          >
            {i + 1}. {label}
          </li>
        ))}
      </ol>

      {error && <p className="text-sm text-red-600">{error}</p>}

      {step === 1 && (
        <form onSubmit={createOrgStep} className="space-y-3">
          <h2 className="text-xl font-semibold">Your organization</h2>
          <input
            className="w-full rounded border px-3 py-2"
            placeholder="Organization name"
            value={orgName}
            onChange={(e) => setOrgName(e.target.value)}
            required
          />
          <input
            className="w-full rounded border px-3 py-2"
            placeholder="PAN/VAT number"
            value={panVat}
            onChange={(e) => setPanVat(e.target.value)}
          />
          <label className="flex items-center gap-2 text-sm">
            <input
              type="checkbox"
              checked={vatRegistered}
              onChange={(e) => setVatRegistered(e.target.checked)}
            />
            VAT registered
          </label>
          <button
            type="submit"
            disabled={loading}
            className="rounded bg-black px-4 py-2 text-white disabled:opacity-50"
          >
            {loading ? "..." : "Next"}
          </button>
        </form>
      )}

      {step === 2 && (
        <form onSubmit={createGymStep} className="space-y-3">
          <h2 className="text-xl font-semibold">Your first branch</h2>
          <input
            className="w-full rounded border px-3 py-2"
            placeholder="Branch code (e.g. KTM1)"
            value={gymCode}
            onChange={(e) => setGymCode(e.target.value)}
            required
          />
          <input
            className="w-full rounded border px-3 py-2"
            placeholder="Branch name"
            value={gymName}
            onChange={(e) => setGymName(e.target.value)}
            required
          />
          <input
            className="w-full rounded border px-3 py-2"
            placeholder="City"
            value={city}
            onChange={(e) => setCity(e.target.value)}
          />
          <button
            type="submit"
            disabled={loading}
            className="rounded bg-black px-4 py-2 text-white disabled:opacity-50"
          >
            {loading ? "..." : "Next"}
          </button>
        </form>
      )}

      {step === 3 && (
        <div className="space-y-3">
          <h2 className="text-xl font-semibold">Membership plans</h2>
          <p className="text-sm opacity-70">
            We&apos;ll set up default membership plans for you here — this comes with billing, in a
            later release. You can skip this for now and add plans afterward.
          </p>
          <button
            type="button"
            onClick={() => {
              setStep(4);
              tokenStore.setOnboardingProgress({ step: 4, orgId });
            }}
            className="rounded bg-black px-4 py-2 text-white"
          >
            Next
          </button>
        </div>
      )}

      {step === 4 && (
        <div className="space-y-3">
          <h2 className="text-xl font-semibold">Invite your team</h2>
          <form onSubmit={sendInvite} className="flex gap-2">
            <select
              className="rounded border px-3 py-2"
              value={inviteRole}
              onChange={(e) => setInviteRole(e.target.value)}
            >
              <option value="manager">Manager</option>
              <option value="front_desk">Front desk</option>
              <option value="trainer">Trainer</option>
            </select>
            <button
              type="submit"
              disabled={loading}
              className="rounded bg-black px-4 py-2 text-white disabled:opacity-50"
            >
              {loading ? "..." : "Create invite link"}
            </button>
          </form>
          {inviteLink && (
            <p className="break-all rounded border bg-neutral-50 p-3 text-xs dark:bg-neutral-900">
              {inviteLink}
              <br />
              <span className="opacity-60">Valid for 72 hours. Share it with the new staff member.</span>
            </p>
          )}
          <button
            type="button"
            onClick={() => {
              tokenStore.clearOnboardingProgress();
              if (gymId) router.push(`/${gymId}`);
            }}
            className="rounded border px-4 py-2"
          >
            Done — go to dashboard
          </button>
        </div>
      )}
    </main>
  );
}
