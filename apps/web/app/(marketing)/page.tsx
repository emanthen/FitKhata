import { MarketingHero } from "@/components/marketing/hero";
import { MarketingFeatures } from "@/components/marketing/features";
import { MarketingHowItWorks } from "@/components/marketing/how-it-works";
import { MarketingProductPreview } from "@/components/marketing/product-preview";
import { MarketingCredibility } from "@/components/marketing/credibility";
import { MarketingPricing } from "@/components/marketing/pricing";
import { MarketingFaq } from "@/components/marketing/faq";
import { MarketingCtaBand } from "@/components/marketing/cta-band";

export default function MarketingHomePage() {
  return (
    <>
      <MarketingHero />
      <MarketingFeatures />
      <MarketingHowItWorks />
      <MarketingProductPreview />
      <MarketingCredibility />
      <MarketingPricing />
      <MarketingFaq />
      <MarketingCtaBand />
    </>
  );
}
