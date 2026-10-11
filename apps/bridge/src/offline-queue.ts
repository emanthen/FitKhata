import { appendFileSync, existsSync, mkdirSync, readFileSync, renameSync, writeFileSync } from "node:fs";
import { dirname } from "node:path";

import type { DeadCheckin, PendingCheckin } from "./types.js";

/** Durable local buffer for check-ins the API hasn't accepted yet.
 *
 * Append-only JSON-lines file, not SQLite: a gate's offline buffer is a few
 * hundred rows at most between network outages, and a flat file needs no
 * native build (better-sqlite3 has no prebuilt binary for every Node/arch
 * combo a Windows PC or Raspberry Pi in the field might run) -- see the
 * plan's note on this swap.
 *
 * Durability order matters: a row is appended to disk BEFORE any network
 * attempt is made, so a crash mid-delivery just means the row gets resent
 * next time -- and resent with the SAME client_uuid, which is what makes a
 * resend safe (the API's unique constraint on (client_uuid, check_in_at)
 * turns a duplicate POST into a no-op `duplicates` entry, not a second row).
 */
export class OfflineQueue {
  constructor(
    private readonly pendingPath: string,
    private readonly deadPath: string = pendingPath.replace(/\.jsonl$/, ".dead.jsonl")
  ) {
    const dir = dirname(pendingPath);
    if (!existsSync(dir)) mkdirSync(dir, { recursive: true });
  }

  enqueue(row: PendingCheckin): void {
    appendFileSync(this.pendingPath, JSON.stringify(row) + "\n", "utf8");
  }

  /** Non-destructive peek at up to `limit` oldest pending rows. */
  dequeueBatch(limit: number): PendingCheckin[] {
    return this._readLines(this.pendingPath).slice(0, limit);
  }

  size(): number {
    return this._readLines(this.pendingPath).length;
  }

  /** Remove rows (by client_uuid) that were successfully delivered --
   * `accepted` and `duplicates` both count, since a duplicate means the
   * server already has the row from an earlier attempt. */
  ack(clientUuids: Iterable<string>): void {
    const acked = new Set(clientUuids);
    if (acked.size === 0) return;
    const remaining = this._readLines(this.pendingPath).filter(
      (row) => !acked.has(row.client_uuid)
    );
    this._atomicWrite(this.pendingPath, remaining);
  }

  /** Move unprocessable rows (e.g. unknown member_code) out of the pending
   * queue so they don't get retried forever; logged to a dead-letter file
   * instead of silently dropped. */
  deadLetter(rows: { client_uuid: string; reason: string }[]): void {
    const reasonByUuid = new Map(rows.map((r) => [r.client_uuid, r.reason]));
    if (reasonByUuid.size === 0) return;

    const pending = this._readLines(this.pendingPath);
    const remaining = pending.filter((row) => !reasonByUuid.has(row.client_uuid));
    const dead: DeadCheckin[] = pending
      .filter((row) => reasonByUuid.has(row.client_uuid))
      .map((row) => ({
        ...row,
        reason: reasonByUuid.get(row.client_uuid)!,
        dead_at: new Date().toISOString(),
      }));

    this._atomicWrite(this.pendingPath, remaining);
    for (const row of dead) {
      appendFileSync(this.deadPath, JSON.stringify(row) + "\n", "utf8");
    }
  }

  private _readLines(path: string): PendingCheckin[] {
    if (!existsSync(path)) return [];
    const text = readFileSync(path, "utf8");
    return text
      .split("\n")
      .filter((line) => line.trim().length > 0)
      .map((line) => JSON.parse(line) as PendingCheckin);
  }

  private _atomicWrite(path: string, rows: PendingCheckin[]): void {
    const tmpPath = `${path}.tmp`;
    const content = rows.map((row) => JSON.stringify(row)).join("\n") + (rows.length ? "\n" : "");
    writeFileSync(tmpPath, content, "utf8");
    renameSync(tmpPath, path);
  }
}
