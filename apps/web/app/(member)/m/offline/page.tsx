import { getTranslations } from "next-intl/server";

// Static — no data fetching. Serwist's `fallbacks` config (app/sw.ts) serves
// this for any /m/** navigation that fails while offline and isn't already
// precached.
export default async function MemberOfflinePage() {
  const t = await getTranslations("member");
  return (
    <div className="space-y-2 text-center">
      <h1 className="text-xl font-semibold">{t("offlineTitle")}</h1>
      <p className="opacity-70">{t("offlineBody")}</p>
    </div>
  );
}
