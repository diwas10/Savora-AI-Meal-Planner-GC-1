export type { components, paths } from "./openapi";

export type Schema<K extends keyof import("./openapi").components["schemas"]> =
  import("./openapi").components["schemas"][K];
