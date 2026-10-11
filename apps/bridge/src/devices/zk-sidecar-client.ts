import { createInterface } from "node:readline";
import type { Readable, Writable } from "node:stream";

export interface SidecarIO {
  stdin: Writable;
  stdout: Readable;
}

export interface SidecarAttendanceRow {
  user_id: string;
  timestamp: string;
}

/** JSON-lines request/response client for sidecar/zk_sidecar.py. Strictly
 * one-in-one-out (no request IDs) -- matches the sidecar's own read-one-
 * line-reply-one-line loop, so requests are queued and resolved in order. */
export class ZkSidecarClient {
  private readonly pending: ((line: string) => void)[] = [];

  constructor(private readonly io: SidecarIO) {
    createInterface({ input: io.stdout }).on("line", (line) => {
      const resolve = this.pending.shift();
      if (resolve) resolve(line);
    });
  }

  private send<T extends Record<string, unknown>>(command: T): Promise<Record<string, unknown>> {
    return new Promise((resolve, reject) => {
      this.pending.push((line) => {
        let parsed: { ok: boolean; error?: string } & Record<string, unknown>;
        try {
          parsed = JSON.parse(line);
        } catch (err) {
          reject(err as Error);
          return;
        }
        if (parsed.ok) resolve(parsed);
        else reject(new Error(parsed.error ?? "sidecar reported an error"));
      });
      this.io.stdin.write(JSON.stringify(command) + "\n");
    });
  }

  connect(host: string, port: number): Promise<void> {
    return this.send({ cmd: "connect", host, port }).then(() => undefined);
  }

  async pollAttendance(
    sinceOffset: number
  ): Promise<{ rows: SidecarAttendanceRow[]; nextOffset: number }> {
    const result = await this.send({ cmd: "poll_attendance", since_offset: sinceOffset });
    return {
      rows: result.rows as SidecarAttendanceRow[],
      nextOffset: result.next_offset as number,
    };
  }

  setUser(userId: string, name: string): Promise<void> {
    return this.send({ cmd: "set_user", user_id: userId, name }).then(() => undefined);
  }

  deleteUser(userId: string): Promise<void> {
    return this.send({ cmd: "delete_user", user_id: userId }).then(() => undefined);
  }

  setEnabled(userId: string, enabled: boolean): Promise<void> {
    return this.send({ cmd: enabled ? "enable_user" : "disable_user", user_id: userId }).then(
      () => undefined
    );
  }

  ping(): Promise<void> {
    return this.send({ cmd: "ping" }).then(() => undefined);
  }
}
