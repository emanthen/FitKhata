"use client";

import { useEffect, useState } from "react";
import { useTranslations } from "next-intl";
import { listStaffRoles, type StaffRole } from "@fitkhata/api-client";
import { IdCard, TriangleAlert } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Card, CardContent } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { StaffTabs } from "@/components/staff/staff-tabs";

export default function StaffPage() {
  const t = useTranslations("admin");
  const [roles, setRoles] = useState<StaffRole[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    // A 403 here redirects to /403 globally (see packages/api-client's
    // http-client) before this ever runs — this catch is for other
    // failures (network, 500).
    listStaffRoles()
      .then(setRoles)
      .catch(() => setError(t("staffLoadError")));
  }, [t]);

  return (
    <div className="space-y-4">
      <h1 className="flex items-center gap-2 text-xl font-semibold tracking-tight">
        <IdCard size={18} strokeWidth={2} className="text-primary" />
        {t("staffPageTitle")}
      </h1>
      <StaffTabs />
      {error && (
        <p className="flex items-center gap-1.5 text-sm text-destructive">
          <TriangleAlert size={14} strokeWidth={2} />
          {error}
        </p>
      )}
      <Card>
        <CardContent>
          {!roles && !error && <Skeleton className="h-40 w-full" />}
          {roles && (
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b text-left text-muted-foreground">
                  <th className="py-1.5">{t("staffColumnUser")}</th>
                  <th className="py-1.5">{t("staffColumnRole")}</th>
                  <th className="py-1.5">{t("staffColumnScope")}</th>
                  <th className="py-1.5">{t("staffColumnActive")}</th>
                </tr>
              </thead>
              <tbody>
                {roles.map((role) => (
                  <tr key={role.id} className="border-b">
                    <td className="font-dashboard-mono py-1.5 text-xs">{role.user}</td>
                    <td className="py-1.5 capitalize">{role.role}</td>
                    <td className="py-1.5">
                      {role.gym ? t("staffScopeBranch") : t("staffScopeAllBranches")}
                    </td>
                    <td className="py-1.5">
                      <Badge variant={role.is_active ? "default" : "secondary"}>
                        {role.is_active ? t("staffActiveYes") : t("staffActiveNo")}
                      </Badge>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
