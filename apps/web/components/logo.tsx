"use client";

import { motion, useReducedMotion } from "motion/react";

// One brand mark, used as-is on every surface (dashboard/marketing/pwa) —
// unlike body type, the logotype itself isn't supposed to re-skin per
// surface. Scan-frame corners + a target dot read as "QR check-in", the
// product's core action, instead of a generic checkmark. Motion is
// mount-only, never looping, per prefers-reduced-motion.
export function Logo({ size = 28, withWordmark = true }: { size?: number; withWordmark?: boolean }) {
  const reduce = useReducedMotion();

  return (
    <span className="inline-flex items-center gap-2">
      <motion.svg
        width={size}
        height={size}
        viewBox="0 0 28 28"
        fill="none"
        initial={reduce ? false : { scale: 0.6, rotate: -8, opacity: 0 }}
        animate={{ scale: 1, rotate: 0, opacity: 1 }}
        transition={{ type: "spring", stiffness: 260, damping: 18 }}
      >
        <rect width="28" height="28" rx="7" className="fill-primary" />
        <path
          d="M8 12V8h4M16 8h4v4M20 16v4h-4M12 20H8v-4"
          stroke="white"
          strokeWidth="2"
          strokeLinecap="round"
          strokeLinejoin="round"
        />
        <circle cx="14" cy="14" r="2" className="fill-accent" />
      </motion.svg>
      {withWordmark && (
        <span className="text-sm font-bold tracking-tight">FitKhata</span>
      )}
    </span>
  );
}
