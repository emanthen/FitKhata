"use client";

import { useTranslations } from "next-intl";
import { motion, useReducedMotion } from "motion/react";
import { Banknote, CalendarClock, TrendingUp, Users } from "lucide-react";

import { StatTile } from "@/components/stat-tile";
import { Badge } from "@/components/ui/badge";
import { Table, TableBody, TableCell, TableRow } from "@/components/ui/table";

// Illustrative numbers for the preview card only — not live data, and not
// wired to any API. Real, locale-appropriate example names rather than
// "John Doe" placeholders.
const EXAMPLE_MEMBERS = [
  { name: "Sabina Thapa", plan: "Pro - 6 month", status: "active" as const },
  { name: "Rajesh Karki", plan: "Starter - monthly", status: "expiring" as const },
  { name: "Anita Gurung", plan: "Pro - annual", status: "active" as const },
];

const STATUS_VARIANT = {
  active: "default",
  expiring: "secondary",
} as const;

export function MarketingProductPreview() {
  const t = useTranslations("marketing");
  const reduce = useReducedMotion();

  return (
    <section className="mx-auto max-w-7xl px-4 py-16 md:px-6 md:py-24">
      <div className="mx-auto max-w-2xl text-center">
        <h2 className="font-marketing-display text-4xl font-bold tracking-tight md:text-5xl">
          {t("productPreviewHeading")}
        </h2>
        <p className="mt-3 text-muted-foreground">{t("productPreviewBody")}</p>
      </div>

      <div className="relative mx-auto mt-12 max-w-4xl">
        <Badge className="absolute -top-3 left-6 z-10 text-[10px]">{t("productPreviewTag")}</Badge>
        <motion.div
          initial={reduce ? false : { opacity: 0, y: 24 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true, amount: 0.3 }}
          transition={{ duration: 0.5, ease: [0.16, 1, 0.3, 1] }}
          className="font-dashboard overflow-hidden rounded-2xl bg-card shadow-2xl shadow-primary/10"
        >
          <div className="grid grid-cols-2 gap-3 p-4 pt-6 sm:grid-cols-4">
            <StatTile label="Active members" icon={<Users size={16} strokeWidth={2} />} value="247" />
            <StatTile
              label="Revenue this month"
              icon={<Banknote size={16} strokeWidth={2} />}
              value="Rs 4,12,990"
            />
            <StatTile label="Renewals due (7d)" icon={<CalendarClock size={16} strokeWidth={2} />} value="18" />
            <StatTile label="Growth" icon={<TrendingUp size={16} strokeWidth={2} />} value="+12%" />
          </div>

          <div className="border-t px-4 pb-4">
            <Table>
              <TableBody>
                {EXAMPLE_MEMBERS.map((m) => (
                  <TableRow key={m.name}>
                    <TableCell className="font-medium">{m.name}</TableCell>
                    <TableCell className="font-dashboard-mono text-muted-foreground">{m.plan}</TableCell>
                    <TableCell className="text-right">
                      <Badge variant={STATUS_VARIANT[m.status]}>{m.status}</Badge>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </div>
        </motion.div>
      </div>
    </section>
  );
}
