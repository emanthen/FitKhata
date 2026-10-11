"use client";

import { useEffect, useState } from "react";
import { useTranslations } from "next-intl";
import { listMemberAnnouncements } from "@fitkhata/api-client";
import { Megaphone, X } from "lucide-react";

import { getCachedPass } from "@/lib/member/pass";

const DISMISSED_KEY = "fitkhata.member.dismissed-announcements";

function getDismissedIds(): string[] {
  try {
    return JSON.parse(localStorage.getItem(DISMISSED_KEY) ?? "[]");
  } catch {
    return [];
  }
}

export function AnnouncementBanner() {
  const t = useTranslations("member");
  const [announcements, setAnnouncements] = useState<
    { id: string; title: string; body: string }[]
  >([]);

  useEffect(() => {
    const pass = getCachedPass();
    if (!pass) return;
    listMemberAnnouncements(pass.token)
      .then((data) => {
        const dismissed = getDismissedIds();
        setAnnouncements(data.filter((a) => !dismissed.includes(a.id)));
      })
      .catch(() => setAnnouncements([]));
  }, []);

  function dismiss(id: string) {
    const dismissed = getDismissedIds();
    localStorage.setItem(DISMISSED_KEY, JSON.stringify([...dismissed, id]));
    setAnnouncements((prev) => prev.filter((a) => a.id !== id));
  }

  if (announcements.length === 0) return null;

  return (
    <div className="mb-4 space-y-2">
      {announcements.map((a) => (
        <div key={a.id} className="rounded-xl border border-accent/30 bg-accent/10 p-3 text-sm">
          <div className="flex items-start justify-between gap-2">
            <div className="flex gap-2">
              <Megaphone size={15} strokeWidth={2} className="mt-0.5 shrink-0 text-accent" />
              <div>
                <p className="font-medium">{a.title}</p>
                <p className="text-foreground/80">{a.body}</p>
              </div>
            </div>
            <button
              onClick={() => dismiss(a.id)}
              aria-label={t("announcementsDismiss")}
              className="shrink-0 rounded p-0.5 text-muted-foreground hover:text-foreground"
            >
              <X size={14} strokeWidth={2} />
            </button>
          </div>
        </div>
      ))}
    </div>
  );
}
