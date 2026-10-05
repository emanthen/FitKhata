import { defineConfig } from "orval";

export default defineConfig({
  fitkhata: {
    input: "./openapi.json",
    output: {
      target: "./src/generated.ts",
      client: "react-query",
      httpClient: "axios",
      override: {
        mutator: {
          path: "./src/http-client.ts",
          name: "httpClient",
        },
      },
    },
  },
});
