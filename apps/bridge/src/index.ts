import { createServer } from "node:http";

const port = Number(process.env.PORT ?? 7070);

const server = createServer((req, res) => {
  if (req.url === "/healthz") {
    res.writeHead(200, { "content-type": "application/json" });
    res.end(JSON.stringify({ status: "ok" }));
    return;
  }
  res.writeHead(404).end();
});

server.listen(port, () => {
  console.log(`fitkhata-bridge listening on :${port}`);
});
