import { useTranslations } from "next-intl";

export default function MarketingHomePage() {
  const t = useTranslations("marketing");
  return (
    <div>
      <h1 className="text-4xl font-bold">{t("heroTitle")}</h1>
      <p className="mt-4 text-lg opacity-80">{t("heroSubtitle")}</p>
    </div>
  );
}
