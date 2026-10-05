import { defineConfig } from "vitest/config";

/** Separate from vitest.config.ts on purpose: the soak script is slow-ish,
 * deliberately not part of `pnpm test`/CI, and needs its own include glob
 * so the default run never picks it up. `pnpm soak:gate` runs it.
 */
export default defineConfig({
  test: {
    environment: "node",
    include: ["e2e/soak-gate-sync.ts"],
  },
});
