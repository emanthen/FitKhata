/** Decodes a JWT's payload for display only — never trust this for
 * authorization, which the API always re-derives from StaffRole fresh on
 * every request. No signature verification; that's the server's job. */

export interface AccessTokenClaims {
  user_id: string;
  org_id: string | null;
  gym_ids: string[];
  role: string | null;
  exp: number;
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
