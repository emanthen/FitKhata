"use client";

import { useEffect, useState } from "react";

import { pendingCount } from "./db";
import { getBackoffMs, refreshSnapshot, syncOutbox } from "./sync";

export interface GateSyncStatus {
  online: boolean;
  pending: number;
  syncError: boolean;
}

const POLL_MS = 5_000;
const SNAPSHOT_REFRESH_MS = 5 * 60 * 1000;

export function useGateSync(): GateSyncStatus {
  const [state, setState] = useState<GateSyncStatus>({
    online: true,
    pending: 0,
    syncError: false,
  });

  useEffect(() => {
    let cancelled = false;
    let syncTimer: ReturnType<typeof setTimeout>;

    async function tick() {
      const result = await syncOutbox();
      const pending = await pendingCount();
      if (!cancelled) {
        setState({ online: navigator.onLine, pending, syncError: result === "sync-error" });
      }
      syncTimer = setTimeout(tick, result === "sync-error" ? getBackoffMs() : POLL_MS);
    }

    tick();

    function handleOnlineChange() {
      tick();
    }
    window.addEventListener("online", handleOnlineChange);
    window.addEventListener("offline", handleOnlineChange);

    function maybeRefreshSnapshot() {
      if (navigator.onLine) refreshSnapshot().catch(() => {});
    }
    maybeRefreshSnapshot();
    const snapshotInterval = setInterval(maybeRefreshSnapshot, SNAPSHOT_REFRESH_MS);

    return () => {
      cancelled = true;
      clearTimeout(syncTimer);
      clearInterval(snapshotInterval);
      window.removeEventListener("online", handleOnlineChange);
      window.removeEventListener("offline", handleOnlineChange);
    };
  }, []);

  return state;
}
