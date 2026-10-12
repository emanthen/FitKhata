"use client";

import { useEffect, useState } from "react";
import { useTranslations } from "next-intl";
import { tokenStore } from "@fitkhata/api-client";

import { useAuth } from "@/lib/auth";

function formatRemaining(expEpochSeconds: number): string {
  const seconds = Math.max(0, Math.floor(expEpochSeconds - Date.now() / 1000));
  const m = Math.floor(seconds / 60);
  const s = seconds % 60;
  return `${m}:${s.toString().padStart(2, "0")}`;
}

/** FR-11.6: shown on every page for the duration of an impersonation
 * session — distinct red accent from the amber ReadOnlyBanner so the two
 * are never visually confused.
 */
export function ImpersonationBanner() {
  const t = useTranslations("admin");
  const { claims } = useAuth();
  const [, forceTick] = useState(0);

  useEffect(() => {
    if (!claims?.impersonator_id) return;
    const id = setInterval(() => forceTick((n) => n + 1), 1000);
    return () => clearInterval(id);
  }, [claims?.impersonator_id]);

  if (!claims?.impersonator_id) return null;

  function exit() {
    tokenStore.endImpersonation();
    // Restores the platform staffer's own session, which has no gym of its
    // own — straight back to the console, not through redirectAfterAuth
    // (which would send a gym-less identity to /onboarding).
    window.location.href = "/platform/tenants";
  }

  return (
    <div className="mb-4 flex items-center justify-between rounded border border-red-200 bg-red-50 p-3 text-sm dark:border-red-900 dark:bg-red-950">
      <p className="text-red-800 dark:text-red-300">
        {t.rich("platformImpersonationBannerText", {
          time: () => (
            <span className="font-mono font-medium">{formatRemaining(claims.exp)}</span>
          ),
        })}
      </p>
      <button
        onClick={exit}
        className="shrink-0 rounded border border-red-300 px-2 py-1 text-xs font-medium text-red-800 hover:bg-red-100 dark:border-red-800 dark:text-red-200 dark:hover:bg-red-900"
      >
        {t("platformImpersonationExitButton")}
      </button>
    </div>
  );
}
