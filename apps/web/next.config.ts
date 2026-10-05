import type { NextConfig } from "next";
import createNextIntlPlugin from "next-intl/plugin";
import withSerwistInit from "@serwist/next";

const withNextIntl = createNextIntlPlugin("./i18n/request.ts");

// Disabled in dev: precaching fights the dev server's own HMR/webpack
// output, which isn't a stable asset list to precache anyway. The gate and
// member PWAs only need the service worker in a real build.
const withSerwist = withSerwistInit({
  swSrc: "app/sw.ts",
  swDest: "public/sw.js",
  disable: process.env.NODE_ENV === "development",
  // The gate kiosk's own outbox/sync loop (lib/gate/sync.ts) already
  // reacts to the `online` event — a full page reload on top of that
  // would yank away whatever scan result is on screen the instant Wi-Fi
  // blips back, which is the opposite of what a public-facing kiosk
  // should do.
  reloadOnOnline: false,
});

const nextConfig: NextConfig = {
  output: "standalone",
  poweredByHeader: false,
};

export default withSerwist(withNextIntl(nextConfig));
