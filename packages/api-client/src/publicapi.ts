import { httpClient } from "./http-client";

// FR-12.3/12.4: owner-facing API key + webhook management
// (publicapi.permissions.IsOwner, gated behind the "public_api" feature —
// Enterprise-only). The actual public read API these keys unlock
// (/api/public/v1/...) is consumed by third parties, not this web app.

export type ApiKeyScope = "members:read" | "memberships:read" | "invoices:read";

export interface ApiKey {
  id: string;
  name: string;
  key_prefix: string;
  scopes: ApiKeyScope[];
  created_at: string;
  last_used_at: string | null;
  revoked_at: string | null;
}

export interface ApiKeyWithSecret extends ApiKey {
  key: string; // only ever present once, on the create response
}

export const listApiKeys = (): Promise<ApiKey[]> =>
  httpClient({ method: "GET", url: "/api/v1/integrations/api-keys" });

export const createApiKey = (data: { name: string; scopes: ApiKeyScope[] }): Promise<ApiKeyWithSecret> =>
  httpClient({ method: "POST", url: "/api/v1/integrations/api-keys", data });

export const revokeApiKey = (id: string): Promise<void> =>
  httpClient({ method: "POST", url: `/api/v1/integrations/api-keys/${id}/revoke` });

export type WebhookEvent = "member.created" | "payment.completed" | "checkin.created";

export interface WebhookSubscription {
  id: string;
  url: string;
  events: WebhookEvent[];
  is_active: boolean;
  created_at: string;
}

export const listWebhookSubscriptions = (): Promise<WebhookSubscription[]> =>
  httpClient({ method: "GET", url: "/api/v1/integrations/webhooks" });

export const createWebhookSubscription = (data: {
  url: string;
  events: WebhookEvent[];
  secret: string;
}): Promise<WebhookSubscription> =>
  httpClient({ method: "POST", url: "/api/v1/integrations/webhooks", data });

export interface WebhookDelivery {
  id: string;
  event: string;
  status: "pending" | "delivered" | "failed";
  attempt_count: number;
  response_status: number | null;
  created_at: string;
  last_attempted_at: string | null;
}

export const listWebhookDeliveries = (subscriptionId: string): Promise<WebhookDelivery[]> =>
  httpClient({
    method: "GET",
    url: `/api/v1/integrations/webhooks/${subscriptionId}/deliveries`,
  });
