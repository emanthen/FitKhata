"use client";

/** Live occupancy for the dashboard (FR-10.1) — connects to the websocket
 * already built in Phase 3 (attendance.consumers.GymFeedConsumer), nothing
 * new on the backend. Derives the ws(s):// origin from the same
 * NEXT_PUBLIC_API_URL the REST client uses.
 */
import { useEffect, useState } from "react";
import { tokenStore } from "@fitkhata/api-client";

function wsUrlFor(gymId: string, token: string): string {
  const apiUrl = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";
  const wsOrigin = apiUrl.replace(/^http/, "ws");
  return `${wsOrigin}/ws/gym/${gymId}/feed?token=${encodeURIComponent(token)}`;
}

export function useGymFeed(gymId: string): number | null {
  const [occupancy, setOccupancy] = useState<number | null>(null);

  useEffect(() => {
    const token = tokenStore.getAccess();
    if (!token) return;

    const socket = new WebSocket(wsUrlFor(gymId, token));
    socket.onmessage = (event) => {
      const payload = JSON.parse(event.data) as { type: string; count?: number };
      if (payload.type === "occupancy" && typeof payload.count === "number") {
        setOccupancy(payload.count);
      } else if (payload.type === "checkin") {
        setOccupancy((prev) => (prev === null ? prev : prev + 1));
      }
    };

    return () => socket.close();
  }, [gymId]);

  return occupancy;
}
