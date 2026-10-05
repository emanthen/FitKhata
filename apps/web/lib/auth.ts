"use client";

import { useCallback, useEffect, useState } from "react";
import { myGyms, tokenStore } from "@fitkhata/api-client";

import { decodeAccessToken, type AccessTokenClaims } from "./jwt";

export function useAuth() {
  const [claims, setClaims] = useState<AccessTokenClaims | null>(null);
  const [ready, setReady] = useState(false);

  useEffect(() => {
    const access = tokenStore.getAccess();
    setClaims(access ? decodeAccessToken(access) : null);
    setReady(true);
  }, []);

  const logout = useCallback(() => {
    tokenStore.clear();
    setClaims(null);
    window.location.href = "/login";
  }, []);

  return { claims, isAuthenticated: !!claims, ready, logout };
}

/** After login/register/invite-accept: pick a gym (the one just onboarded,
 * or the first accessible one) and land in the admin area, or send a
 * brand-new owner with no gym yet to onboarding. */
export async function redirectAfterAuth(onNavigate: (path: string) => void): Promise<void> {
  // A gym id picked in a previous session (or by a previous user on a
  // shared browser) would otherwise ride along as X-Gym-Id on this call —
  // TenantMiddleware 403s outright for a gym this identity has no role on,
  // before MyGymsView (which doesn't need a gym) ever runs.
  tokenStore.clearActiveGymId();
  const gyms = await myGyms();
  if (gyms.length === 0) {
    onNavigate("/onboarding");
    return;
  }
  tokenStore.setActiveGymId(gyms[0].id);
  onNavigate(`/${gyms[0].id}`);
}
