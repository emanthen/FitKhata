import { httpClient } from "./http-client";

export interface Organization {
  id: string;
  name: string;
  pan_vat_no: string;
  is_vat_registered: boolean;
  vat_inclusive_pricing: boolean;
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
  settings: {
    warning_days: number;
    red_list_days: number;
    anti_passback_min: number;
    notification_events?: Record<string, boolean>;
    notification_channel_order?: string[];
  };
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

export const getGymSettings = (): Promise<Gym> =>
  httpClient({ method: "GET", url: "/api/v1/gyms/settings" });

export const updateGymSettings = (data: Partial<Gym>): Promise<Gym> =>
  httpClient({ method: "PATCH", url: "/api/v1/gyms/settings", data });

export const getOrgSettings = (): Promise<Organization> =>
  httpClient({ method: "GET", url: "/api/v1/orgs/settings" });

export const updateOrgSettings = (data: Partial<Organization>): Promise<Organization> =>
  httpClient({ method: "PATCH", url: "/api/v1/orgs/settings", data });
