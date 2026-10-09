"use client";

import { useEffect, useState } from "react";
import { useTranslations } from "next-intl";

/** sw.ts sets skipWaiting:true, so a new service worker activates itself —
 * there's no "waiting" state to prompt the user into. The only thing worth
 * surfacing is that the page the user is looking at was served by the old
 * version, via the controllerchange event that fires the instant the new
 * worker takes over.
 */
export function UpdateToast() {
  const t = useTranslations("member");
  const [show, setShow] = useState(false);

  useEffect(() => {
    if (!("serviceWorker" in navigator)) return;
    const onControllerChange = () => setShow(true);
    navigator.serviceWorker.addEventListener("controllerchange", onControllerChange);
    return () =>
      navigator.serviceWorker.removeEventListener("controllerchange", onControllerChange);
  }, []);

  if (!show) return null;

  return (
    <div className="fixed inset-x-4 bottom-4 z-50 flex items-center justify-between gap-3 rounded border bg-background px-4 py-3 text-sm shadow-lg">
      <span>{t("updateAvailable")}</span>
      <button
        onClick={() => window.location.reload()}
        className="shrink-0 rounded bg-black px-3 py-1.5 text-white"
      >
        {t("updateReload")}
      </button>
    </div>
  );
}
