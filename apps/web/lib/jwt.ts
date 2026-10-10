/** Decodes a JWT's payload for display only — never trust this for
 * authorization, which the API always re-derives from StaffRole fresh on
 * every request. No signature verification; that's the server's job. */

export interface AccessTokenClaims {
  user_id: string;
  org_id: string | null;
  gym_ids: string[];
  role: string | null;
  exp: number;
  // Phase 11 — FitKhata platform staff, not a gym StaffRole. Gates the
  // (superadmin) route group client-side; the API re-checks via
  // saas.permissions.IsPlatformStaff on every request regardless.
  is_platform_staff?: boolean;
  // Present only on an impersonation token (saas.services.start_impersonation).
  impersonator_id?: string;
}

export function decodeAccessToken(token: string): AccessTokenClaims | null {
  try {
    const payload = token.split(".")[1];
    const base64 = payload.replace(/-/g, "+").replace(/_/g, "/");
    const json = decodeURIComponent(
      atob(base64)
        .split("")
        .map((c) => "%" + c.charCodeAt(0).toString(16).padStart(2, "0"))
        .join("")
    );
    return JSON.parse(json);
  } catch {
    return null;
  }
}
