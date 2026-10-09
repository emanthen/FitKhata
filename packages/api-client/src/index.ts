// Hand-written client for the endpoints that exist so far — reliable
// without a live codegen round-trip. `make schema` can still regenerate
// src/generated.ts from the API's OpenAPI schema via orval once that's
// worth it; nothing here blocks that path.
export { httpClient } from "./http-client";
export { tokenStore } from "./token-store";
export * from "./auth";
export * from "./gyms";
export * from "./staff";
export * from "./members";
export * from "./billing";
export * from "./attendance";
export * from "./retention";
export * from "./notifications";
export * from "./coaching";
