"use client";

import { useEffect, useState } from "react";
import { listStaffRoles, type StaffRole } from "@fitkhata/api-client";

import { StaffTabs } from "@/components/staff/staff-tabs";

export default function StaffPage() {
  const [roles, setRoles] = useState<StaffRole[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    // A 403 here redirects to /403 globally (see packages/api-client's
    // http-client) before this ever runs — this catch is for other
    // failures (network, 500).
    listStaffRoles()
      .then(setRoles)
      .catch(() => setError("Couldn't load staff — try again shortly."));
  }, []);

  return (
    <div className="space-y-4">
      <h1 className="text-2xl font-semibold">Staff</h1>
      <StaffTabs />
      {error && <p className="text-sm text-red-600">{error}</p>}
      {roles && (
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b text-left opacity-60">
              <th className="py-1">User</th>
              <th className="py-1">Role</th>
              <th className="py-1">Scope</th>
              <th className="py-1">Active</th>
            </tr>
          </thead>
          <tbody>
            {roles.map((role) => (
              <tr key={role.id} className="border-b">
                <td className="py-1 font-mono text-xs">{role.user}</td>
                <td className="py-1">{role.role}</td>
                <td className="py-1">{role.gym ? "This branch" : "All branches"}</td>
                <td className="py-1">{role.is_active ? "Yes" : "No"}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  );
}
