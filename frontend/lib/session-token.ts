/**
 * BFF session-token minting (ADR-0009).
 *
 * This is the Next.js side of the auth contract: after Auth.js verifies the user's
 * session, we mint a short-lived HS256 token carrying a narrow claim set and forward
 * it to the FastAPI backend, which verifies it in `app/infra/auth.py`. The claim names
 * here MUST match what the backend's `decode_session` expects.
 *
 * The signing secret (AUTH_SECRET) is shared with the backend and never reaches the
 * browser — this module runs only on the server.
 */
import { SignJWT } from "jose";

const ISSUER = "advisory-bff";
const AUDIENCE = "advisory-api";
const TTL_SECONDS = 300; // short-lived; freshness comes from re-checking the real session

export interface SessionIdentity {
  userId: string;
  activeOrg: string;
  globalRoles?: string[];
  orgRoles?: Record<string, string[]>;
  sessionVersion?: number;
}

export async function mintServiceToken(identity: SessionIdentity): Promise<string> {
  const secret = process.env.AUTH_SECRET;
  if (!secret) {
    throw new Error("AUTH_SECRET is not configured");
  }
  const key = new TextEncoder().encode(secret);
  const now = Math.floor(Date.now() / 1000);

  return new SignJWT({
    org: identity.activeOrg,
    global_roles: identity.globalRoles ?? [],
    org_roles: identity.orgRoles ?? {},
    sv: identity.sessionVersion ?? 0,
  })
    .setProtectedHeader({ alg: "HS256" })
    .setSubject(identity.userId)
    .setIssuer(ISSUER)
    .setAudience(AUDIENCE)
    .setIssuedAt(now)
    .setExpirationTime(now + TTL_SECONDS)
    .sign(key);
}
