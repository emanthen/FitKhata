"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { myGyms, tokenStore, type MyGym } from "@fitkhata/api-client";

export function BranchSwitcher({ activeGymId }: { activeGymId: string }) {
  const router = useRouter();
  const [gyms, setGyms] = useState<MyGym[]>([]);

  useEffect(() => {
    myGyms().then(setGyms);
  }, []);

  function switchTo(gymId: string) {
    tokenStore.setActiveGymId(gymId);
    router.push(`/${gymId}`);
  }

  if (gyms.length <= 1) {
    return <span className="text-sm font-medium">{gyms[0]?.name ?? "..."}</span>;
  }

  return (
    <select
      className="rounded border px-2 py-1 text-sm"
      value={activeGymId}
      onChange={(e) => switchTo(e.target.value)}
    >
      {gyms.map((gym) => (
        <option key={gym.id} value={gym.id}>
          {gym.name}
        </option>
      ))}
    </select>
  );
}
