import type { MetadataRoute } from "next";

// A separate installable-PWA identity from the gate kiosk's root
// public/manifest.json (landscape/fullscreen, start_url "/gate") — this one
// is portrait/standalone for a member's own phone. Reuses the gate's theme
// colors and public/icons/icon.svg (a single scalable mark, no reason to
// generate a second icon set for FR-8.1).
export default function manifest(): MetadataRoute.Manifest {
  return {
    name: "FitKhata",
    short_name: "फिटखाता",
    description: "Your gym membership, pass and plan",
    start_url: "/m",
    display: "standalone",
    orientation: "portrait",
    background_color: "#1c1a14",
    theme_color: "#1c1a14",
    icons: [
      {
        src: "/icons/icon.svg",
        sizes: "any",
        type: "image/svg+xml",
        purpose: "any",
      },
    ],
  };
}
