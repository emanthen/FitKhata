"use client";

import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { fetchVatRegisterExport, getVatRegister } from "@fitkhata/api-client";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { ReportsTabs } from "@/components/reports/reports-tabs";
import { useAuth } from "@/lib/auth";
import { formatNpr } from "@/lib/money";

async function downloadExport(fiscalYear: number, format: "csv" | "xlsx" | "pdf") {
  const blob = await fetchVatRegisterExport(fiscalYear, format);
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = `vat-register-${fiscalYear}.${format}`;
  a.click();
  URL.revokeObjectURL(url);
}

export default function VatRegisterPage() {
  const { claims } = useAuth();
  const [fiscalYear, setFiscalYear] = useState("");
  const parsedYear = Number(fiscalYear);
  const isOwner = claims?.role === "owner";

  const query = useQuery({
    queryKey: ["reports", "vat-register", fiscalYear],
    queryFn: () => getVatRegister(parsedYear),
    enabled: isOwner && fiscalYear.length > 0 && !Number.isNaN(parsedYear),
  });

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-semibold">Reports</h1>
      <ReportsTabs />

      {!isOwner ? (
        <p className="text-sm opacity-60">Only an owner can view the VAT sales register.</p>
      ) : (
        <>
          <div className="flex items-end gap-4">
            <div className="space-y-1">
              <Label htmlFor="fiscal-year">Fiscal year (BS)</Label>
              <Input
                id="fiscal-year"
                placeholder="2083"
                value={fiscalYear}
                onChange={(e) => setFiscalYear(e.target.value)}
                className="w-28"
              />
            </div>
            {fiscalYear && (
              <div className="flex gap-2">
                <Button variant="outline" onClick={() => downloadExport(parsedYear, "csv")}>
                  CSV
                </Button>
                <Button variant="outline" onClick={() => downloadExport(parsedYear, "xlsx")}>
                  XLSX
                </Button>
                <Button variant="outline" onClick={() => downloadExport(parsedYear, "pdf")}>
                  PDF
                </Button>
              </div>
            )}
          </div>

          {query.isLoading && <p className="text-sm opacity-60">Loading...</p>}

          {query.data && (
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b text-left opacity-60">
                    <th className="py-1">Bill date (BS)</th>
                    <th className="py-1">Bill no.</th>
                    <th className="py-1">Buyer name</th>
                    <th className="py-1">Buyer PAN</th>
                    <th className="py-1 text-right">Taxable</th>
                    <th className="py-1 text-right">VAT</th>
                    <th className="py-1 text-right">Total</th>
                  </tr>
                </thead>
                <tbody>
                  {query.data.rows.map((row) => (
                    <tr key={row.number} className="border-b">
                      <td className="py-1.5">{row.bill_date_bs}</td>
                      <td className="py-1.5">{row.number}</td>
                      <td className="py-1.5">{row.buyer_name}</td>
                      <td className="py-1.5">{row.buyer_pan}</td>
                      <td className="py-1.5 text-right">{formatNpr(row.taxable_npr)}</td>
                      <td className="py-1.5 text-right">{formatNpr(row.vat_npr)}</td>
                      <td className="py-1.5 text-right">{formatNpr(row.total_npr)}</td>
                    </tr>
                  ))}
                  {query.data.rows.length === 0 && (
                    <tr>
                      <td colSpan={7} className="py-3 text-center text-sm opacity-60">
                        No issued invoices for this fiscal year.
                      </td>
                    </tr>
                  )}
                </tbody>
              </table>
            </div>
          )}
        </>
      )}
    </div>
  );
}
