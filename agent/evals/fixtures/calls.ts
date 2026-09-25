import type { FixtureApi } from "./api-server";

/** `METHOD /path` for every request the fixture received after `mark`. */
export function callsSince(api: FixtureApi, mark: number): string[] {
  return api.requests
    .slice(mark)
    .map((request) => `${request.method} ${request.path}`);
}

/** `METHOD /path` pairs with their JSON bodies, for asserting on what was sent. */
export function postsSince(
  api: FixtureApi,
  mark: number,
): { path: string; body: unknown }[] {
  return api.requests
    .slice(mark)
    .filter((request) => request.method === "POST")
    .map((request) => ({ path: request.path, body: request.body }));
}
