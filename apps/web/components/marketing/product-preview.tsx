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
        <h2 className="text-3xl font-bold tracking-tight md:text-4xl">
          {t("productPreviewHeading")}
        </h2>
        <p className="mt-3 text-muted-foreground">{t("productPreviewBody")}</p>
      </div>

      <motion.div
        initial={reduce ? false : { opacity: 0, y: 24 }}
        whileInView={{ opacity: 1, y: 0 }}
        viewport={{ once: true, amount: 0.3 }}
        transition={{ duration: 0.5, ease: [0.16, 1, 0.3, 1] }}
        className="font-dashboard mx-auto mt-10 max-w-4xl overflow-hidden rounded-2xl border bg-card shadow-xl"
      >
        <div className="flex items-center gap-1.5 border-b bg-muted/40 px-4 py-2.5">
          <span className="size-2.5 rounded-full bg-destructive/40" />
          <span className="size-2.5 rounded-full bg-accent/40" />
          <span className="size-2.5 rounded-full bg-primary/40" />
          <span className="ml-3 rounded-md bg-background px-2.5 py-0.5 text-xs text-muted-foreground">
            app.fitkhata.com/demo-gym
          </span>
          <Badge variant="outline" className="ml-auto text-[10px] text-muted-foreground">
            {t("productPreviewTag")}
          </Badge>
        </div>

        <div className="grid grid-cols-2 gap-3 p-4 sm:grid-cols-4">
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
    </section>
  );
}
