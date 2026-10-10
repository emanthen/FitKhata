const ACCESS_KEY = "fitkhata.access";
const REFRESH_KEY = "fitkhata.refresh";
const GYM_KEY = "fitkhata.activeGymId";
const ONBOARDING_KEY = "fitkhata.onboardingProgress";
// Session-scoped (not localStorage, same reasoning as onboarding progress
// below): a platform staffer's own session stashed here for the duration
// of one impersonation, so "exit impersonation" can restore it.
const PLATFORM_BACKUP_KEY = "fitkhata.platformSessionBackup";

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
  // Phase 11 impersonation: stashes the platform staffer's own access+
  // refresh before switching to the impersonation access token (which has
  // no refresh token of its own — it's deliberately single-shot and
  // time-boxed; once it expires the next refresh attempt fails and
  // httpClient's own interceptor clears the session, a safe hard-stop
  // rather than silently reverting mid-session).
  beginImpersonation: (access: string): void => {
    if (!isBrowser()) return;
    const current = tokenStore.getAccess();
    const refresh = tokenStore.getRefresh();
    if (current && refresh) {
      sessionStorage.setItem(PLATFORM_BACKUP_KEY, JSON.stringify({ access: current, refresh }));
    }
    localStorage.setItem(ACCESS_KEY, access);
    localStorage.removeItem(REFRESH_KEY);
  },
  isImpersonating: (): boolean =>
    isBrowser() ? sessionStorage.getItem(PLATFORM_BACKUP_KEY) !== null : false,
  endImpersonation: (): void => {
    if (!isBrowser()) return;
    const raw = sessionStorage.getItem(PLATFORM_BACKUP_KEY);
    sessionStorage.removeItem(PLATFORM_BACKUP_KEY);
    if (!raw) {
      tokenStore.clear();
      return;
    }
    try {
      const { access, refresh } = JSON.parse(raw) as { access: string; refresh: string };
      tokenStore.setTokens(access, refresh);
    } catch {
      tokenStore.clear();
    }
  },
};
