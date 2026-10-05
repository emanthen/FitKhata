const ACCESS_KEY = "fitkhata.access";
const REFRESH_KEY = "fitkhata.refresh";
const GYM_KEY = "fitkhata.activeGymId";
const ONBOARDING_KEY = "fitkhata.onboardingProgress";

const isBrowser = () => typeof window !== "undefined";

export interface OnboardingProgress {
  step: 1 | 2 | 3 | 4;
  orgId: string | null;
}

export const tokenStore = {
  getAccess: (): string | null => (isBrowser() ? localStorage.getItem(ACCESS_KEY) : null),
  getRefresh: (): string | null => (isBrowser() ? localStorage.getItem(REFRESH_KEY) : null),
  setTokens: (access: string, refresh: string): void => {
    if (!isBrowser()) return;
    localStorage.setItem(ACCESS_KEY, access);
    localStorage.setItem(REFRESH_KEY, refresh);
  },
  clear: (): void => {
    if (!isBrowser()) return;
    localStorage.removeItem(ACCESS_KEY);
    localStorage.removeItem(REFRESH_KEY);
    localStorage.removeItem(GYM_KEY);
    sessionStorage.removeItem(ONBOARDING_KEY);
  },
  getActiveGymId: (): string | null => (isBrowser() ? localStorage.getItem(GYM_KEY) : null),
  setActiveGymId: (gymId: string): void => {
    if (!isBrowser()) return;
    localStorage.setItem(GYM_KEY, gymId);
  },
  clearActiveGymId: (): void => {
    if (!isBrowser()) return;
    localStorage.removeItem(GYM_KEY);
  },
  // Session-scoped (not localStorage): onboarding progress shouldn't outlive
  // the tab, and — like activeGymId — must never ride along into a
  // different identity's session (see clearOnboardingProgress).
  getOnboardingProgress: (): OnboardingProgress | null => {
    if (!isBrowser()) return null;
    try {
      const raw = sessionStorage.getItem(ONBOARDING_KEY);
      return raw ? (JSON.parse(raw) as OnboardingProgress) : null;
    } catch {
      return null;
    }
  },
  setOnboardingProgress: (progress: OnboardingProgress): void => {
    if (!isBrowser()) return;
    sessionStorage.setItem(ONBOARDING_KEY, JSON.stringify(progress));
  },
  // Must run on every fresh login/register (see redirectAfterAuth) — not
  // just logout — otherwise a second identity signing in on the same tab
  // inherits the previous identity's in-progress orgId/step.
  clearOnboardingProgress: (): void => {
    if (!isBrowser()) return;
    sessionStorage.removeItem(ONBOARDING_KEY);
  },
};
