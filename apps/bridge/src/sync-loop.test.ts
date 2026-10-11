import { randomUUID } from "node:crypto";
import { mkdtempSync, rmSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";

import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { OfflineQueue } from "./offline-queue.js";
import { flushOnce } from "./sync-loop.js";
import type { BatchCheckinResult, PendingCheckin } from "./types.js";

let dir: string;
let queue: OfflineQueue;

beforeEach(() => {
  dir = mkdtempSync(join(tmpdir(), "fitkhata-bridge-test-"));
  queue = new OfflineQueue(join(dir, "pending.jsonl"));
});

afterEach(() => {
  rmSync(dir, { recursive: true, force: true });
});

function makeRow(overrides: Partial<PendingCheckin> = {}): PendingCheckin {
  return {
    client_uuid: randomUUID(),
    member_code: "GYM1-0001",
    check_in_at: new Date().toISOString(),
    source: "biometric",
    created_at: new Date().toISOString(),
    ...overrides,
  };
}

describe("offline queue + sync loop", () => {
  it("keeps a row queued when the network attempt fails", async () => {
    const row = makeRow();
    queue.enqueue(row);

    const sendBatch = vi.fn().mockRejectedValue(new Error("network down"));
    const outcome = await flushOnce(queue, sendBatch);

    expect(outcome.delivered).toBe(0);
    expect(queue.size()).toBe(1);
  });

  it("removes a row once the server accepts it", async () => {
    const row = makeRow();
    queue.enqueue(row);

    const sendBatch = vi.fn().mockResolvedValue({
      accepted: [row.client_uuid],
      duplicates: [],
      rejected: [],
    } satisfies BatchCheckinResult);

    const outcome = await flushOnce(queue, sendBatch);

    expect(outcome.delivered).toBe(1);
    expect(queue.size()).toBe(0);
  });

  it("clears a row on replay even when the server reports it as a duplicate, and never resends it with a new client_uuid", async () => {
    // Simulates: first attempt's request reached the server and committed,
    // but the response was lost (crash/timeout) before the bridge could
    // ack it locally -- so the row is still in the queue on the next tick.
    const row = makeRow();
    queue.enqueue(row);

    const sendBatch = vi.fn().mockResolvedValue({
      accepted: [],
      duplicates: [row.client_uuid],
      rejected: [],
    } satisfies BatchCheckinResult);

    const outcome = await flushOnce(queue, sendBatch);

    expect(outcome.delivered).toBe(1);
    expect(queue.size()).toBe(0);
    // The only batch ever sent used the original client_uuid -- confirms
    // a replay never mints a second client_uuid for the same event.
    expect(sendBatch).toHaveBeenCalledTimes(1);
    expect(sendBatch.mock.calls[0][0]).toEqual([row]);
  });

  it("moves an unprocessable row to the dead-letter file instead of retrying forever", async () => {
    const row = makeRow({ member_code: "DOES-NOT-EXIST" });
    queue.enqueue(row);

    const sendBatch = vi.fn().mockResolvedValue({
      accepted: [],
      duplicates: [],
      rejected: [{ client_uuid: row.client_uuid, reason: "member not found" }],
    } satisfies BatchCheckinResult);

    const outcome = await flushOnce(queue, sendBatch);

    expect(outcome.delivered).toBe(0);
    expect(queue.size()).toBe(0); // no longer pending

    // A second flush must not resend it -- it's in the dead-letter file now.
    await flushOnce(queue, sendBatch);
    expect(sendBatch).toHaveBeenCalledTimes(1);
  });

  it("does nothing when the queue is empty", async () => {
    const sendBatch = vi.fn();
    const outcome = await flushOnce(queue, sendBatch);

    expect(outcome.delivered).toBe(0);
    expect(sendBatch).not.toHaveBeenCalled();
  });

  it("delivers zero duplicate rows across a full crash-and-retry cycle", async () => {
    // End-to-end of the spec's own test ask: "offline buffering replay with
    // 0 duplicates". Enqueue 3 rows, fail once (simulating the bridge being
    // offline), then succeed -- assert every row is delivered exactly once
    // and the batch contents never change between the failed and
    // successful attempt (same client_uuids, same order).
    const rows = [makeRow(), makeRow(), makeRow()];
    for (const row of rows) queue.enqueue(row);

    const sendBatch = vi
      .fn()
      .mockRejectedValueOnce(new Error("network down"))
      .mockResolvedValueOnce({
        accepted: rows.map((r) => r.client_uuid),
        duplicates: [],
        rejected: [],
      } satisfies BatchCheckinResult);

    const firstAttempt = await flushOnce(queue, sendBatch);
    expect(firstAttempt.delivered).toBe(0);
    expect(queue.size()).toBe(3);

    const secondAttempt = await flushOnce(queue, sendBatch);
    expect(secondAttempt.delivered).toBe(3);
    expect(queue.size()).toBe(0);

    expect(sendBatch.mock.calls[0][0]).toEqual(rows);
    expect(sendBatch.mock.calls[1][0]).toEqual(rows);
  });
});
