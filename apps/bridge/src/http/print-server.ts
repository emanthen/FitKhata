import { createServer, type IncomingMessage, type Server, type ServerResponse } from "node:http";

export interface PrintServerConfig {
  webOrigin: string; // e.g. https://app.fitkhata.com -- the only origin allowed to print
  printToken: string; // per-device shared secret, issued at pairing time
  port?: number;
}

export type PrintHandler = (body: unknown) => Promise<void>;

function readBody(req: IncomingMessage): Promise<string> {
  return new Promise((resolve, reject) => {
    let data = "";
    req.on("data", (chunk) => (data += chunk));
    req.on("end", () => resolve(data));
    req.on("error", reject);
  });
}

function originMatches(req: IncomingMessage, config: PrintServerConfig): boolean {
  return req.headers.origin === config.webOrigin;
}

function isAuthorized(req: IncomingMessage, config: PrintServerConfig): boolean {
  if (!originMatches(req, config)) return false;
  const auth = req.headers.authorization ?? "";
  return auth === `Bearer ${config.printToken}`;
}

/** Only set on a matching-origin response -- a wrong-origin browser gets no
 * CORS header at all, so even the 403 body below is unreadable to its JS
 * (the fetch() promise just rejects), not merely logically forbidden. */
function corsHeaders(config: PrintServerConfig): Record<string, string> {
  return {
    "access-control-allow-origin": config.webOrigin,
    "access-control-allow-methods": "POST, OPTIONS",
    "access-control-allow-headers": "content-type, authorization",
  };
}

/** Local-only print endpoint: 127.0.0.1:7777/print, reachable only from the
 * FitKhata web origin (CORS-style Origin check -- a browser tab on any
 * other site can't hit it even via a same-machine fetch) AND only with the
 * per-device token issued at pairing time. Both checks are independent and
 * either one failing is a 403, per the spec's explicit test ask.
 *
 * A JSON POST with an Authorization header is a "non-simple" request, so a
 * real browser sends an OPTIONS preflight before the actual POST -- that
 * preflight carries no Authorization (browsers withhold it until the
 * browser decides the request is allowed), so it's gated on Origin alone;
 * the real auth check still runs on the POST itself. Skipping this preflight
 * handling (as an earlier version of this file did) means the browser never
 * even attempts the real request -- caught by the CORS tests below, which
 * a plain node:http client can't catch since it doesn't enforce CORS. */
export function createPrintServer(config: PrintServerConfig, onPrint: PrintHandler): Server {
  return createServer((req: IncomingMessage, res: ServerResponse) => {
    if (req.url !== "/print") {
      res.writeHead(404).end();
      return;
    }

    if (req.method === "OPTIONS") {
      if (!originMatches(req, config)) {
        res.writeHead(403).end();
        return;
      }
      res.writeHead(204, corsHeaders(config)).end();
      return;
    }

    if (req.method !== "POST") {
      res.writeHead(404).end();
      return;
    }

    if (!isAuthorized(req, config)) {
      res.writeHead(403, { "content-type": "application/json" }).end(
        JSON.stringify({ detail: "Forbidden" })
      );
      return;
    }

    readBody(req)
      .then(async (raw) => {
        const body = raw ? JSON.parse(raw) : {};
        await onPrint(body);
        res
          .writeHead(200, { "content-type": "application/json", ...corsHeaders(config) })
          .end(JSON.stringify({ ok: true }));
      })
      .catch((err: Error) => {
        res
          .writeHead(500, { "content-type": "application/json", ...corsHeaders(config) })
          .end(JSON.stringify({ detail: err.message }));
      });
  });
}
