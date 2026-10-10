"use client";

import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { fetchVatRegisterExport, getVatRegister } from "@fitkhata/api-client";
import { ChartColumn, Download } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Skeleton } from "@/components/ui/skeleton";
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
      <h1 className="flex items-center gap-2 text-xl font-semibold tracking-tight">
        <ChartColumn size={18} strokeWidth={2} className="text-primary" />
        Reports
      </h1>
      <ReportsTabs />

      {!isOwner ? (
        <p className="text-sm text-muted-foreground">
          Only an owner can view the VAT sales register.
        </p>
      ) : (
        <>
          <div className="flex flex-wrap items-end gap-4">
            <div className="space-y-1.5">
              <Label htmlFor="fiscal-year">Fiscal year (BS)</Label>
              <Input
                id="fiscal-year"
                placeholder="2083"
                value={fiscalYear}
                onChange={(e) => setFiscalYear(e.target.value)}
                className="h-8 w-28"
              />
            </div>
            {fiscalYear && (
              <div className="flex gap-2">
                <Button variant="outline" size="sm" onClick={() => downloadExport(parsedYear, "csv")}>
                  <Download size={13} strokeWidth={2} data-icon="inline-start" />
                  CSV
                </Button>
                <Button variant="outline" size="sm" onClick={() => downloadExport(parsedYear, "xlsx")}>
                  <Download size={13} strokeWidth={2} data-icon="inline-start" />
                  XLSX
                </Button>
                <Button variant="outline" size="sm" onClick={() => downloadExport(parsedYear, "pdf")}>
                  <Download size={13} strokeWidth={2} data-icon="inline-start" />
                  PDF
                </Button>
              </div>
            )}
          </div>

          <Card>
            <CardContent>
              {query.isLoading && <Skeleton className="h-40 w-full" />}

              {query.data && (
                <div className="overflow-x-auto">
                  <table className="w-full text-sm">
                    <thead>
                      <tr className="border-b text-left text-muted-foreground">
                        <th className="py-1.5">Bill date (BS)</th>
                        <th className="py-1.5">Bill no.</th>
                        <th className="py-1.5">Buyer name</th>
                        <th className="py-1.5">Buyer PAN</th>
                        <th className="py-1.5 text-right">Taxable</th>
                        <th className="py-1.5 text-right">VAT</th>
                        <th className="py-1.5 text-right">Total</th>
                      </tr>
                    </thead>
                    <tbody className="font-dashboard-mono">
                      {query.data.rows.map((row) => (
                        <tr key={row.number} className="border-b">
                          <td className="py-1.5">{row.bill_date_bs}</td>
                          <td className="py-1.5">{row.number}</td>
                          <td className="py-1.5 font-sans">{row.buyer_name}</td>
                          <td className="py-1.5">{row.buyer_pan}</td>
                          <td className="py-1.5 text-right">{formatNpr(row.taxable_npr)}</td>
                          <td className="py-1.5 text-right">{formatNpr(row.vat_npr)}</td>
                          <td className="py-1.5 text-right">{formatNpr(row.total_npr)}</td>
                        </tr>
                      ))}
                      {query.data.rows.length === 0 && (
                        <tr>
                          <td colSpan={7} className="py-6 text-center font-sans text-sm text-muted-foreground">
                            No issued invoices for this fiscal year.
                          </td>
                        </tr>
                      )}
                    </tbody>
                  </table>
                </div>
              )}
            </CardContent>
          </Card>
        </>
      )}
    </div>
  );
}
