"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { useTranslations } from "next-intl";
import { fetchMemberInvoicePdf, listMemberInvoices, type Invoice } from "@fitkhata/api-client";

import { getCachedPass } from "@/lib/member/pass";

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

  if (!invoices) return null;

  return (
    <div className="space-y-4">
      <h1 className="text-2xl font-semibold">{t("invoicesTitle")}</h1>

      {invoices.length === 0 ? (
        <p className="text-sm opacity-60">{t("invoicesNone")}</p>
      ) : (
        <ul className="space-y-2">
          {invoices.map((inv) => (
            <li
              key={inv.id}
              className="flex items-center justify-between rounded border px-3 py-2 text-sm"
            >
              <span>
                {inv.number}
                <span className="ml-2 opacity-60">NPR {inv.total_npr}</span>
              </span>
              <button onClick={() => download(inv.id, inv.number)} className="text-xs underline">
                {t("invoicesDownload")}
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
