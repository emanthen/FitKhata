import { getTranslations } from "next-intl/server";
import { WifiOff } from "lucide-react";

// Static — no data fetching. Serwist's `fallbacks` config (app/sw.ts) serves
// this for any /m/** navigation that fails while offline and isn't already
// precached.
export default async function MemberOfflinePage() {
  const t = await getTranslations("member");
  return (
    <div className="flex flex-col items-center gap-2 pt-12 text-center">
      <WifiOff size={28} strokeWidth={1.75} className="mb-1 text-muted-foreground" />
      <h1 className="text-lg font-semibold tracking-tight">{t("offlineTitle")}</h1>
      <p className="text-sm text-muted-foreground">{t("offlineBody")}</p>
    </div>
  );
}
