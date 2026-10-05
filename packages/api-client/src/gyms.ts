import { httpClient } from "./http-client";

export interface Organization {
  id: string;
  name: string;
  pan_vat_no: string;
  is_vat_registered: boolean;
  saas_plan: string;
  saas_status: string;
  created_at: string;
}

export interface Gym {
  id: string;
  org: string;
  code: string;
  name: string;
  address: string;
  city: string;
  phone: string;
  timezone: string;
  settings: { warning_days: number; red_list_days: number; anti_passback_min: number };
  created_at: string;
}

export interface MyGym {
  id: string;
  org_id: string;
  code: string;
  name: string;
  city: string;
}

export const createOrganization = (data: {
  name: string;
  pan_vat_no?: string;
  is_vat_registered?: boolean;
}): Promise<Organization> =>
  httpClient({ method: "POST", url: "/api/v1/orgs", data });

export const createGym = (data: {
  org: string;
  code: string;
  name: string;
  address?: string;
  city?: string;
  phone?: string;
}): Promise<Gym> => httpClient({ method: "POST", url: "/api/v1/gyms", data });

export const myGyms = (): Promise<MyGym[]> => httpClient({ method: "GET", url: "/api/v1/gyms/mine" });
