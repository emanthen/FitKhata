"use client";

import { useEffect, useState } from "react";
import { useTranslations } from "next-intl";
import { listMemberAnnouncements } from "@fitkhata/api-client";

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
        <div key={a.id} className="rounded border border-amber-200 bg-amber-50 p-3 text-sm dark:border-amber-900 dark:bg-amber-950">
          <div className="flex items-start justify-between gap-2">
            <div>
              <p className="font-medium">{a.title}</p>
              <p className="opacity-80">{a.body}</p>
            </div>
            <button
              onClick={() => dismiss(a.id)}
              className="shrink-0 text-xs underline opacity-60"
            >
              {t("announcementsDismiss")}
            </button>
          </div>
        </div>
      ))}
    </div>
  );
}
