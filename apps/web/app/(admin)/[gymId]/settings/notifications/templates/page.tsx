"use client";

import { useState } from "react";
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

import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";

const CHANNELS: { value: NotificationChannel; label: string }[] = [
  { value: "sms", label: "SMS" },
  { value: "whatsapp", label: "WhatsApp" },
  { value: "push", label: "Push" },
  { value: "email", label: "Email" },
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
        className="h-28 w-full rounded border p-2 text-sm"
      />
      <div className="rounded border bg-muted/30 p-2 text-sm">
        <p className="mb-1 text-xs font-medium opacity-60">Preview</p>
        {renderPreview(body)}
      </div>
      <Button size="sm" onClick={save} disabled={saving}>
        {saving ? "..." : override ? "Update" : "Save override"}
      </Button>
    </div>
  );
}

export default function TemplateEditorPage() {
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
    <div className="max-w-3xl space-y-6">
      <h1 className="text-2xl font-semibold">Notification templates</h1>
      <p className="text-sm opacity-60">
        Editing here creates your own override for this branch&apos;s organization — the
        platform default stays as the fallback for every key/channel/language you haven&apos;t
        customized.
      </p>

      <div className="flex flex-wrap gap-3">
        <div className="space-y-1">
          <Label htmlFor="template-key">Event</Label>
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
        <div className="space-y-1">
          <Label htmlFor="template-channel">Channel</Label>
          <Select value={channel} onValueChange={(v) => setChannel(v as NotificationChannel)}>
            <SelectTrigger id="template-channel" className="w-40">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              {CHANNELS.map((c) => (
                <SelectItem key={c.value} value={c.value}>
                  {c.label}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
      </div>

      <div className="grid grid-cols-1 gap-6 md:grid-cols-2">
        <LanguageEditor
          key={`${key}-${channel}-ne`}
          language="ne"
          label="Nepali"
          override={neOverride}
          defaultBody={neDefault}
          onSaved={refresh}
          templateKey={key}
          channel={channel}
        />
        <LanguageEditor
          key={`${key}-${channel}-en`}
          language="en"
          label="English"
          override={enOverride}
          defaultBody={enDefault}
          onSaved={refresh}
          templateKey={key}
          channel={channel}
        />
      </div>
    </div>
  );
}
