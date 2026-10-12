"use client";

import { useState } from "react";
import { useTranslations } from "next-intl";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import {
  createTemplate,
  listDefaultTemplates,
  listTemplates,
  TEMPLATE_KEYS,
  updateTemplate,
  type NotificationChannel,
  type Page,
  type Template,
  type TemplateKey,
} from "@fitkhata/api-client";
import { MessageSquareText } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";

const CHANNELS: { value: NotificationChannel; labelKey: string }[] = [
  { value: "sms", labelKey: "notifChannelSms" },
  { value: "whatsapp", labelKey: "notifChannelWhatsapp" },
  { value: "push", labelKey: "notifChannelPush" },
  { value: "email", labelKey: "notifChannelEmail" },
];

// Sample values for the live preview — not what a real event would send,
// just enough to show how the {{variable}} placeholders render.
const PREVIEW_CONTEXT: Record<string, string> = {
  name: "Ram Shrestha",
  amount: "3000.00",
  invoice_number: "2082-00042",
  start_date: "2026-10-15",
  end_date: "2026-10-20",
  class_name: "Morning Yoga",
  date: "2026-10-10",
  promo_code: "WELCOME10",
};

function renderPreview(body: string): string {
  return body.replace(/\{\{\s*(\w+)\s*\}\}/g, (_match, key: string) => PREVIEW_CONTEXT[key] ?? "");
}

function unwrap<T>(data: T[] | Page<T> | undefined): T[] {
  if (!data) return [];
  return Array.isArray(data) ? data : data.results;
}

function LanguageEditor({
  language,
  label,
  override,
  defaultBody,
  onSaved,
  templateKey,
  channel,
}: {
  language: "ne" | "en";
  label: string;
  override: Template | undefined;
  defaultBody: string;
  onSaved: () => void;
  templateKey: TemplateKey;
  channel: NotificationChannel;
}) {
  const t = useTranslations("admin");
  const [body, setBody] = useState(override?.body ?? defaultBody);
  const [saving, setSaving] = useState(false);

  async function save() {
    setSaving(true);
    try {
      if (override) {
        await updateTemplate(override.id, { body });
      } else {
        await createTemplate({ key: templateKey, channel, language, body });
      }
      onSaved();
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="space-y-2">
      <Label>{label}</Label>
      <textarea
        value={body}
        onChange={(e) => setBody(e.target.value)}
        className="h-28 w-full rounded-lg border border-input bg-transparent p-2.5 text-sm outline-none focus-visible:border-ring focus-visible:ring-3 focus-visible:ring-ring/50"
      />
      <div className="rounded-lg border bg-muted/40 p-2.5 text-sm">
        <p className="mb-1 text-xs font-medium text-muted-foreground">{t("notifTemplatePreview")}</p>
        {renderPreview(body)}
      </div>
      <Button size="sm" onClick={save} disabled={saving}>
        {saving ? "..." : override ? t("notifTemplateUpdate") : t("notifTemplateSaveOverride")}
      </Button>
    </div>
  );
}

export default function TemplateEditorPage() {
  const t = useTranslations("admin");
  const queryClient = useQueryClient();
  const [key, setKey] = useState<TemplateKey>(TEMPLATE_KEYS[0]);
  const [channel, setChannel] = useState<NotificationChannel>("sms");

  const defaults = useQuery({
    queryKey: ["notification-templates", "defaults", key],
    queryFn: () => listDefaultTemplates(key),
  });
  const overrides = useQuery({
    queryKey: ["notification-templates", "overrides"],
    queryFn: listTemplates,
  });

  const overrideList = unwrap(overrides.data);
  const defaultList = defaults.data ?? [];

  const neDefault = defaultList.find((t) => t.channel === channel && t.language === "ne")?.body ?? "";
  const enDefault = defaultList.find((t) => t.channel === channel && t.language === "en")?.body ?? "";
  const neOverride = overrideList.find((t) => t.key === key && t.channel === channel && t.language === "ne");
  const enOverride = overrideList.find((t) => t.key === key && t.channel === channel && t.language === "en");

  function refresh() {
    queryClient.invalidateQueries({ queryKey: ["notification-templates"] });
  }

  return (
    <div className="max-w-3xl space-y-5">
      <div>
        <h1 className="flex items-center gap-2 text-xl font-semibold tracking-tight">
          <MessageSquareText size={18} strokeWidth={2} className="text-primary" />
          {t("settingsTemplates")}
        </h1>
        <p className="mt-1 text-sm text-muted-foreground">{t("notifTemplateOverrideBody")}</p>
      </div>

      <div className="flex flex-wrap gap-3">
        <div className="space-y-1.5">
          <Label htmlFor="template-key">{t("notifTemplateEventLabel")}</Label>
          <Select value={key} onValueChange={(v) => setKey(v as TemplateKey)}>
            <SelectTrigger id="template-key" className="w-56">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              {TEMPLATE_KEYS.map((k) => (
                <SelectItem key={k} value={k}>
                  {k}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
        <div className="space-y-1.5">
          <Label htmlFor="template-channel">{t("notifChannelLabel")}</Label>
          <Select value={channel} onValueChange={(v) => setChannel(v as NotificationChannel)}>
            <SelectTrigger id="template-channel" className="w-40">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              {CHANNELS.map((c) => (
                <SelectItem key={c.value} value={c.value}>
                  {t(c.labelKey)}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
      </div>

      <Card>
        <CardContent className="grid grid-cols-1 gap-6 md:grid-cols-2">
          <LanguageEditor
            key={`${key}-${channel}-ne`}
            language="ne"
            label={t("notifTemplateLanguageNepali")}
            override={neOverride}
            defaultBody={neDefault}
            onSaved={refresh}
            templateKey={key}
            channel={channel}
          />
          <LanguageEditor
            key={`${key}-${channel}-en`}
            language="en"
            label={t("notifTemplateLanguageEnglish")}
            override={enOverride}
            defaultBody={enDefault}
            onSaved={refresh}
            templateKey={key}
            channel={channel}
          />
        </CardContent>
      </Card>
    </div>
  );
}
