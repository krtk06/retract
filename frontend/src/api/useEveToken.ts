import { useCallback, useRef, useState } from "react";

import { request } from "./client";

/**
 * The eve channel authenticates with a bearer token, but our session cookie is
 * httpOnly — the browser cannot read it. So the backend exchanges the cookie for
 * a short-lived, eve-scoped token (iss=ai-intel, aud=eve-agent) that the agent's
 * `jwtHmac` policy verifies.
 *
 * The token is exposed as a *resolver* rather than a value: eve calls it before
 * every request, so a long-lived tab keeps working after the token expires
 * without rebuilding the client, and the agent can start a session before the
 * first exchange has finished.
 */
const REFRESH_MARGIN_MS = 30_000;

type EveToken = { token: string; expires_in: number };

export function useEveToken() {
  const cache = useRef<{ token: string; expiresAt: number } | null>(null);
  const inFlight = useRef<Promise<string> | null>(null);
  const [error, setError] = useState<string | null>(null);

  const resolve = useCallback(async (): Promise<string> => {
    const cached = cache.current;
    if (cached && cached.expiresAt - REFRESH_MARGIN_MS > Date.now()) {
      return cached.token;
    }
    inFlight.current ??= (async () => {
      try {
        const token = await request<EveToken>("/api/auth/eve-token", { method: "POST" });
        cache.current = { token: token.token, expiresAt: Date.now() + token.expires_in * 1000 };
        setError(null);
        return token.token;
      } catch (cause) {
        setError(cause instanceof Error ? cause.message : "could not authorize the agent");
        throw cause;
      } finally {
        inFlight.current = null;
      }
    })();
    return inFlight.current;
  }, []);

  // eve's TokenValue resolver signature; it must never throw into the client.
  const bearer = useCallback(
    () =>
      resolve().catch(() => {
        throw new Error("agent authorization failed");
      }),
    [resolve],
  );

  return { auth: { bearer } as const, error, resolve };
}
