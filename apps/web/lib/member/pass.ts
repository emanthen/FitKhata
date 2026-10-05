/** Cache for a member's own gate pass, written once after redeeming the
 * signed link (see app/(member)/m/pass/[token]/page.tsx) and read on every
 * later visit to /m — the whole point is that the QR screen keeps working
 * offline after that first redemption, with no further network calls.
 */
export interface CachedPass {
  member_code: string;
  full_name: string;
  gym_code: string;
  qr_secret_hex: string;
}

const KEY = "fitkhata.member.pass";

const isBrowser = () => typeof window !== "undefined";

export function getCachedPass(): CachedPass | null {
  if (!isBrowser()) return null;
  const raw = localStorage.getItem(KEY);
  if (!raw) return null;
  try {
    return JSON.parse(raw) as CachedPass;
  } catch {
    return null;
  }
}

export function setCachedPass(pass: CachedPass): void {
  if (!isBrowser()) return;
  localStorage.setItem(KEY, JSON.stringify(pass));
}
