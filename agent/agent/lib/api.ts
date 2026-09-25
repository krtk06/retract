/**
 * Typed client for the AI Engineering Intelligence API.
 *
 * Every tool in this agent goes through here instead of fetching directly, so
 * credentials, error shape, and the "no RAG" endpoint set stay in one place.
 *
 * Authentication: the agent runs server-side, so it presents the shared
 * `AI_INTEL_AGENT_TOKEN` service secret (backend: `X-Agent-Token`) and the
 * acting user's login (`X-Agent-User`) from the eve session's authenticated
 * principal. Tools never call `/search` — that endpoint no longer exists, and
 * retrieval is served by the symbol graph instead.
 */

const DEFAULT_API_URL = "http://localhost:8110";

export class ApiError extends Error {
  constructor(
    readonly status: number,
    readonly path: string,
    message: string,
  ) {
    super(`${status} ${path}: ${message}`);
    this.name = "ApiError";
  }
}

export type RequestOptions = {
  method?: "GET" | "POST";
  query?: Record<string, string | number | boolean | undefined>;
  body?: unknown;
  /** Login of the user the eve session is acting as. */
  actingAs?: string;
};

/**
 * Read lazily on every call: evals boot a fixture API on an ephemeral port and
 * publish it through the environment after this module is loaded.
 */
function baseUrl(): string {
  return (process.env.AI_INTEL_API_URL ?? DEFAULT_API_URL).replace(/\/$/, "");
}

function agentToken(): string {
  return process.env.AI_INTEL_AGENT_TOKEN ?? "";
}

function buildUrl(path: string, query: RequestOptions["query"]): string {
  const url = new URL(`${baseUrl()}${path}`);
  for (const [key, value] of Object.entries(query ?? {})) {
    if (value !== undefined) url.searchParams.set(key, String(value));
  }
  return url.toString();
}

export async function apiGet<T>(
  path: string,
  options: Omit<RequestOptions, "method" | "body"> = {},
): Promise<T> {
  return request<T>(path, { ...options, method: "GET" });
}

export async function apiPost<T>(
  path: string,
  body: unknown,
  options: Omit<RequestOptions, "method" | "body"> = {},
): Promise<T> {
  return request<T>(path, { ...options, method: "POST", body });
}

async function request<T>(path: string, options: RequestOptions): Promise<T> {
  const token = agentToken();
  if (!token) {
    throw new ApiError(
      0,
      path,
      "AI_INTEL_AGENT_TOKEN is not set; the agent cannot call the API",
    );
  }
  const headers: Record<string, string> = { "X-Agent-Token": token };
  if (options.actingAs) headers["X-Agent-User"] = options.actingAs;
  if (options.body !== undefined) headers["Content-Type"] = "application/json";

  const response = await fetch(buildUrl(path, options.query), {
    method: options.method ?? "GET",
    headers,
    body: options.body === undefined ? undefined : JSON.stringify(options.body),
  });

  if (!response.ok) {
    throw new ApiError(response.status, path, await readError(response));
  }
  if (response.status === 204) return undefined as T;
  return (await response.json()) as T;
}

async function readError(response: Response): Promise<string> {
  const text = await response.text();
  try {
    const parsed: unknown = JSON.parse(text);
    if (parsed && typeof parsed === "object" && "detail" in parsed) {
      return String((parsed as { detail: unknown }).detail);
    }
  } catch {
    return text.slice(0, 300);
  }
  return text.slice(0, 300);
}
