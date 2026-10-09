import { httpClient } from "./http-client";
import type { Page } from "./members";

// --- Templates (FR-6.1) ------------------------------------------------------

export type NotificationChannel = "sms" | "whatsapp" | "push" | "email";
export type TemplateLanguage = "ne" | "en";

export const TEMPLATE_KEYS = [
  "welcome",
  "payment_receipt",
  "expiry_7d",
  "expiry_3d",
  "expiry_1d",
  "expired_1d",
  "expired_7d",
  "birthday",
  "red_list_day7",
  "red_list_day10",
  "freeze_applied",
  "class_booked",
  "winback",
] as const;
export type TemplateKey = (typeof TEMPLATE_KEYS)[number];

export interface Template {
  id: string;
  org: string | null;
  key: TemplateKey;
  channel: NotificationChannel;
  language: TemplateLanguage;
  body: string;
  whatsapp_template_name: string;
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

export const listTemplates = (): Promise<Template[] | Page<Template>> =>
  httpClient({ method: "GET", url: "/api/v1/notifications/templates/" });

export const listDefaultTemplates = (key?: TemplateKey): Promise<Template[]> =>
  httpClient({
    method: "GET",
    url: "/api/v1/notifications/templates/defaults/",
    params: key ? { key } : undefined,
  });

export const createTemplate = (data: {
  key: TemplateKey;
  channel: NotificationChannel;
  language: TemplateLanguage;
  body: string;
  whatsapp_template_name?: string;
}): Promise<Template> =>
  httpClient({ method: "POST", url: "/api/v1/notifications/templates/", data });

export const updateTemplate = (id: string, data: Partial<Template>): Promise<Template> =>
  httpClient({ method: "PATCH", url: `/api/v1/notifications/templates/${id}/`, data });

export const deleteTemplate = (id: string): Promise<void> =>
  httpClient({ method: "DELETE", url: `/api/v1/notifications/templates/${id}/` });

// --- Delivery log (FR-6.5) ----------------------------------------------------

export interface Notification {
  id: string;
  member: string;
  member_name: string;
  channel: NotificationChannel;
  template_key: string;
  language: TemplateLanguage;
  status: "queued" | "sent" | "delivered" | "failed";
  attempt_count: number;
  provider_ref: string;
  cost_npr: string;
  error: string;
  sent_at: string | null;
  delivered_at: string | null;
  fallback_of: string | null;
  created_at: string;
}

export const listNotificationLog = (filters: {
  channel?: NotificationChannel;
  status?: Notification["status"];
  member?: string;
  date_from?: string;
  date_to?: string;
}): Promise<Notification[] | Page<Notification>> =>
  httpClient({ method: "GET", url: "/api/v1/notifications/log/", params: filters });

export const getMonthlyNotificationCost = (): Promise<{ month: string; cost_npr: string }> =>
  httpClient({ method: "GET", url: "/api/v1/notifications/log/monthly_cost/" });

// --- Broadcast (FR-6.4) -------------------------------------------------------

export type BroadcastSegment = "expired" | "red_list" | "plan" | "gender" | "tag";

export interface Broadcast {
  id: string;
  segment: BroadcastSegment;
  segment_value: string;
  channel: NotificationChannel;
  body_ne: string;
  body_en: string;
  recipient_count: number;
  cost_npr: string;
  created_by: string | null;
  sent_at: string | null;
  created_at: string;
}

export const estimateBroadcast = (data: {
  segment: BroadcastSegment;
  segment_value?: string;
  channel: NotificationChannel;
}): Promise<{ recipient_count: number; cost_npr: string }> =>
  httpClient({ method: "POST", url: "/api/v1/notifications/broadcasts/estimate", data });

export const sendBroadcast = (data: {
  segment: BroadcastSegment;
  segment_value?: string;
  channel: NotificationChannel;
  body_ne: string;
  body_en: string;
}): Promise<Broadcast> =>
  httpClient({ method: "POST", url: "/api/v1/notifications/broadcasts/", data });

export const listBroadcasts = (): Promise<Broadcast[] | Page<Broadcast>> =>
  httpClient({ method: "GET", url: "/api/v1/notifications/broadcasts/" });

// --- Announcements (FR-6.7) ---------------------------------------------------

export interface Announcement {
  id: string;
  title: string;
  body_ne: string;
  body_en: string;
  is_active: boolean;
  starts_at: string | null;
  ends_at: string | null;
  created_by: string | null;
  created_at: string;
}

export const listAnnouncements = (): Promise<Announcement[] | Page<Announcement>> =>
  httpClient({ method: "GET", url: "/api/v1/notifications/announcements/" });

export const createAnnouncement = (data: {
  title: string;
  body_ne: string;
  body_en: string;
  starts_at?: string;
  ends_at?: string;
}): Promise<Announcement> =>
  httpClient({ method: "POST", url: "/api/v1/notifications/announcements/", data });

export const updateAnnouncement = (
  id: string,
  data: Partial<Announcement>
): Promise<Announcement> =>
  httpClient({ method: "PATCH", url: `/api/v1/notifications/announcements/${id}/`, data });

// Member-facing (token-authenticated, same pass token as billing's renewal family)

export const listMemberAnnouncements = (
  passToken: string
): Promise<{ id: string; title: string; body: string }[]> =>
  httpClient({ method: "GET", url: `/api/v1/m/pass/${passToken}/announcements` });

export const subscribeToPush = (
  passToken: string,
  data: { endpoint: string; keys: { p256dh: string; auth: string }; user_agent?: string }
): Promise<{ subscribed: boolean }> =>
  httpClient({ method: "POST", url: `/api/v1/m/pass/${passToken}/push-subscribe`, data });
