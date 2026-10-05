import { httpClient } from "./http-client";

export interface StaffRole {
  id: string;
  org: string;
  gym: string | null;
  user: string;
  role: string;
  is_active: boolean;
  created_at: string;
}

export const listStaffRoles = (): Promise<StaffRole[]> =>
  httpClient({ method: "GET", url: "/api/v1/staff-roles/" });
