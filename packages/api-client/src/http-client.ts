import axios, { type AxiosRequestConfig, type InternalAxiosRequestConfig } from "axios";

import { tokenStore } from "./token-store";

const instance = axios.create({
  baseURL: process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000",
});

instance.interceptors.request.use((config) => {
  const access = tokenStore.getAccess();
  if (access) config.headers.set("Authorization", `Bearer ${access}`);
  const gymId = tokenStore.getActiveGymId();
  if (gymId) config.headers.set("X-Gym-Id", gymId);
  return config;
});

interface RetriableConfig extends InternalAxiosRequestConfig {
  _retried?: boolean;
}

let refreshing: Promise<string | null> | null = null;

async function refreshAccessToken(): Promise<string | null> {
  const refresh = tokenStore.getRefresh();
  if (!refresh) return null;
  try {
    const { data } = await axios.post<{ access: string; refresh?: string }>(
      `${instance.defaults.baseURL}/api/v1/auth/token/refresh`,
      { refresh }
    );
    tokenStore.setTokens(data.access, data.refresh ?? refresh);
    return data.access;
  } catch {
    tokenStore.clear();
    return null;
  }
}

instance.interceptors.response.use(
  (response) => response,
  async (error) => {
    const original = error.config as RetriableConfig | undefined;
    if (error.response?.status === 401 && original && !original._retried) {
      original._retried = true;
      refreshing ??= refreshAccessToken();
      const newAccess = await refreshing;
      refreshing = null;
      if (newAccess) {
        original.headers.set("Authorization", `Bearer ${newAccess}`);
        return instance.request(original);
      }
    }
    // A 403 here is always the API's own permission check (StaffRoleViewSet,
    // IsManagerOrAbove, ...) failing — not auth, which is the 401 path above.
    // Send the user to the explanation page rather than every caller having
    // to handle it individually.
    if (error.response?.status === 403 && typeof window !== "undefined") {
      window.location.href = "/403";
    }
    return Promise.reject(error);
  }
);

export async function httpClient<T>(config: AxiosRequestConfig): Promise<T> {
  const { data } = await instance.request<T>(config);
  return data;
}
