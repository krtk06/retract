import { jwtHmac, localDev, none } from "eve/channels/auth";
import { eveChannel } from "eve/channels/eve";

/**
 * The browser's session cookie is httpOnly, so the frontend exchanges it for a
 * short-lived HS256 bearer token (`POST /api/auth/eve-token`) and sends that as
 * `Authorization: Bearer`. The backend mints `iss=ai-intel`, `aud=eve-agent`,
 * so neither token can be replayed against the other service.
 */
const secret = process.env.RETRACT_JWT_SECRET;

const auth = secret
  ? [
      jwtHmac({
        algorithm: "HS256",
        audiences: ["eve-agent"],
        issuer: "ai-intel",
        secret,
      }),
      localDev(),
    ]
  : process.env.NODE_ENV === "production"
    ? // Fail closed: without a shared secret no production caller can be verified.
      [localDev()]
    : [localDev(), none()];

export default eveChannel({ auth });
