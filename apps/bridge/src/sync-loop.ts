import { MAX_BATCH_SIZE } from "./api-client.js";
import type { OfflineQueue } from "./offline-queue.js";
import type { BatchCheckinResult, PendingCheckin } from "./types.js";

export type SendBatchFn = (rows: PendingCheckin[]) => Promise<BatchCheckinResult>;

/** One flush attempt: peek a batch, try to deliver it, reconcile the queue
 * against whatever the server actually says happened. Never throws on a
 * network failure -- the batch just stays queued for the next tick. */
export async function flushOnce(
  queue: OfflineQueue,
  sendBatch: SendBatchFn
): Promise<{ delivered: number }> {
  const batch = queue.dequeueBatch(MAX_BATCH_SIZE);
  if (batch.length === 0) return { delivered: 0 };

  let result: BatchCheckinResult;
  try {
    result = await sendBatch(batch);
  } catch {
    return { delivered: 0 };
  }

  // `duplicates` means the server already committed this row from an
  // earlier attempt whose response was lost -- treated the same as
  // `accepted` for queue purposes, never resent as a "new" client_uuid.
  queue.ack([...result.accepted, ...result.duplicates]);
  queue.deadLetter(result.rejected);

  return { delivered: result.accepted.length + result.duplicates.length };
}

export function startSyncLoop(
  queue: OfflineQueue,
  sendBatch: SendBatchFn,
  intervalMs = 10_000
): () => void {
  const timer = setInterval(() => {
    void flushOnce(queue, sendBatch);
  }, intervalMs);
  return () => clearInterval(timer);
}
