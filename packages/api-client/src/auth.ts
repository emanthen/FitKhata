import { httpClient } from "./http-client";

export interface TokenPair {
  access: string;
  refresh: string;
  requires_totp_setup: boolean;
}

export interface OtpVerifyResult {
  verified: boolean;
  user_exists: boolean;
  access?: string;
  refresh?: string;
  requires_totp_setup?: boolean;
  registration_token?: string;
}

export interface DeviceSession {
  id: string;
  user_agent: string;
  ip: string | null;
  created_at: string;
  last_used_at: string;
  revoked_at: string | null;
}

export const otpSend = (phone: string): Promise<void> =>
  httpClient({ method: "POST", url: "/api/v1/auth/otp/send", data: { phone } });

export const otpVerify = (phone: string, code: string): Promise<OtpVerifyResult> =>
  httpClient({ method: "POST", url: "/api/v1/auth/otp/verify", data: { phone, code } });

export const register = (
  registrationToken: string,
  fullName: string,
  password: string
): Promise<TokenPair> =>
  httpClient({
    method: "POST",
    url: "/api/v1/auth/register",
    data: { registration_token: registrationToken, full_name: fullName, password },
  });

export const login = (
  identifier: string,
  password: string,
  totpCode?: string
): Promise<TokenPair> =>
  httpClient({
    method: "POST",
    url: "/api/v1/auth/login",
    data: { identifier, password, totp_code: totpCode },
  });

export const reissueTokens = (): Promise<TokenPair> =>
  httpClient({ method: "POST", url: "/api/v1/auth/token/reissue" });

export const totpSetup = (): Promise<{ secret: string; otpauth_url: string }> =>
  httpClient({ method: "POST", url: "/api/v1/auth/totp/setup" });

export const totpConfirm = (code: string): Promise<void> =>
  httpClient({ method: "POST", url: "/api/v1/auth/totp/confirm", data: { code } });

export const listSessions = (): Promise<DeviceSession[]> =>
  httpClient({ method: "GET", url: "/api/v1/auth/sessions" });

export const revokeSession = (id: string): Promise<void> =>
  httpClient({ method: "POST", url: `/api/v1/auth/sessions/${id}/revoke` });

export const createInvite = (role: string, gymId?: string): Promise<{ token: string }> =>
  httpClient({
    method: "POST",
    url: "/api/v1/auth/invites",
    data: { role, gym_id: gymId },
  });

export const acceptInvite = (
  token: string,
  phone: string,
  fullName: string,
  password: string
): Promise<TokenPair> =>
  httpClient({
    method: "POST",
    url: "/api/v1/auth/invites/accept",
    data: { token, phone, full_name: fullName, password },
  });
