"use client";

import { useSubscription } from "@/lib/use-feature";

/** FR-11.3 dunning banner — amber-card style mirrors the only existing
 * banner precedent (components/member/announcement-banner.tsx). No
 * dismiss: unlike an announcement, this should reappear every time the
 * condition is still true.
 */
export function ReadOnlyBanner() {
  const { data } = useSubscription();
  if (data?.status !== "read_only" && data?.status !== "suspended") return null;

  return (
    <div className="mb-4 rounded border border-amber-200 bg-amber-50 p-3 text-sm dark:border-amber-900 dark:bg-amber-950">
      <p className="font-medium text-amber-900 dark:text-amber-200">
        Your account is read-only — payment overdue.
      </p>
      <p className="text-amber-800 dark:text-amber-300">
        Check-ins keep working, but new sales and other changes are paused until payment is
        received. Pay the outstanding invoice under Settings → Billing to restore full access.
      </p>
    </div>
  );
}
