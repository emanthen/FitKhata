"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { useTranslations } from "next-intl";
import { fetchMemberInvoicePdf, listMemberInvoices, type Invoice } from "@fitkhata/api-client";
import { Download, Receipt } from "lucide-react";

import { getCachedPass } from "@/lib/member/pass";
import { formatNpr } from "@/lib/money";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";

export default function MemberInvoicesPage() {
  const t = useTranslations("member");
  const router = useRouter();
  const [invoices, setInvoices] = useState<Invoice[] | null>(null);

  useEffect(() => {
    const pass = getCachedPass();
    if (!pass) {
      router.replace("/m");
      return;
    }
    listMemberInvoices(pass.token)
      .then(setInvoices)
      .catch(() => setInvoices([]));
  }, [router]);

  async function download(invoiceId: string, number: string) {
    const pass = getCachedPass();
    if (!pass) return;
    const blob = await fetchMemberInvoicePdf(pass.token, invoiceId);
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `${number}.pdf`;
    a.click();
    URL.revokeObjectURL(url);
  }

  if (!invoices) {
    return (
      <div className="space-y-4">
        <Skeleton className="h-7 w-36" />
        <Skeleton className="h-14 w-full rounded-xl" />
      </div>
    );
  }

  return (
    <div className="space-y-4">
      <h1 className="flex items-center gap-2 text-xl font-semibold tracking-tight">
        <Receipt size={18} strokeWidth={2} className="text-primary" />
        {t("invoicesTitle")}
      </h1>

      {invoices.length === 0 ? (
        <p className="text-sm text-muted-foreground">{t("invoicesNone")}</p>
      ) : (
        <ul className="space-y-2.5">
          {invoices.map((inv) => (
            <li key={inv.id}>
              <Card>
                <CardContent className="flex items-center justify-between py-3">
                  <div>
                    <p className="font-dashboard-mono text-sm">{inv.number}</p>
                    <p className="font-dashboard-mono text-xs text-muted-foreground">
                      {formatNpr(inv.total_npr, { symbol: true })}
                    </p>
                  </div>
                  <Button variant="outline" size="sm" onClick={() => download(inv.id, inv.number)}>
                    <Download size={13} strokeWidth={2} data-icon="inline-start" />
                    {t("invoicesDownload")}
                  </Button>
                </CardContent>
              </Card>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
