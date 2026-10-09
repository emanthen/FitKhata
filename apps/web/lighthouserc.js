/** Performance budget for the Member PWA's home route (NFR-P.3): JS under
 * 200KB gzip, LCP under 2.5s. `formFactor: "mobile"` + `throttlingMethod:
 * "simulate"` is Lighthouse CI's standard mid-tier-Android/slow-network
 * proxy — there's no literal "Moto G Power" preset to select, so this is
 * the practical equivalent rather than an exact device match.
 */
module.exports = {
  ci: {
    collect: {
      startServerCommand: "pnpm start",
      startServerReadyPattern: "Ready in",
      url: ["http://localhost:3000/m"],
      numberOfRuns: 1,
      settings: {
        formFactor: "mobile",
        throttlingMethod: "simulate",
        screenEmulation: { mobile: true, width: 412, height: 823, deviceScaleFactor: 2.625 },
      },
    },
    assert: {
      assertions: {
        "resource-summary:script:size": ["error", { maxNumericValue: 204800 }],
        "largest-contentful-paint": ["error", { maxNumericValue: 2500 }],
      },
    },
    upload: { target: "filesystem", outputDir: "./.lighthouseci" },
  },
};
