import { mintServiceToken, type SessionIdentity } from "./session-token";

const BASE_URL =
  process.env.API_BASE_URL ?? process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000/v1";

export interface AuthMembership {
  organization_id: string;
  organization_name: string;
  organization_slug: string;
  role: string;
}

export interface AuthUser {
  id: string;
  email: string;
  name: string | null;
  email_verified: boolean;
  status: string;
  active_org: string;
  global_roles: string[];
  org_roles: Record<string, string[]>;
  memberships: AuthMembership[];
  session_version: number;
}

async function authRequest(path: string, init: RequestInit = {}): Promise<unknown> {
  const res = await fetch(`${BASE_URL}${path}`, {
    ...init,
    headers: { "Content-Type": "application/json", ...init.headers },
    cache: "no-store",
  });
  const body = await res.json().catch(() => null);
  if (!res.ok) {
    const message = body?.message || body?.error || "Authentication failed";
    throw new Error(message);
  }
  return body;
}

export async function signinWithCredentials(email: string, password: string): Promise<AuthUser> {
  const body = await authRequest("/auth/signin", {
    method: "POST",
    body: JSON.stringify({ email, password }),
  });
  return (body as { user: AuthUser }).user;
}

export async function signupWithCredentials(args: {
  email: string;
  password: string;
  name?: string;
  organization_name: string;
}): Promise<{ user: AuthUser; verification_token: string | null }> {
  return (await authRequest("/auth/signup", {
    method: "POST",
    body: JSON.stringify(args),
  })) as { user: AuthUser; verification_token: string | null };
}

export async function verifyEmail(token: string): Promise<AuthUser> {
  return (await authRequest("/auth/verify-email", {
    method: "POST",
    body: JSON.stringify({ token }),
  })) as AuthUser;
}

export async function requestPasswordReset(email: string): Promise<{ message: string }> {
  return (await authRequest("/auth/forgot-password", {
    method: "POST",
    body: JSON.stringify({ email }),
  })) as { message: string };
}

export async function resetPassword(
  token: string,
  password: string,
): Promise<{ message: string }> {
  return (await authRequest("/auth/reset-password", {
    method: "POST",
    body: JSON.stringify({ token, password }),
  })) as { message: string };
}

export async function switchActiveOrganization(
  identity: SessionIdentity,
  organizationId: string,
): Promise<AuthUser> {
  const token = await mintServiceToken(identity);
  const res = await fetch(`${BASE_URL}/auth/active-organization`, {
    method: "PATCH",
    headers: { Authorization: `Bearer ${token}`, "Content-Type": "application/json" },
    body: JSON.stringify({ organization_id: organizationId }),
    cache: "no-store",
  });
  const body = await res.json().catch(() => null);
  if (!res.ok) throw new Error(body?.message || "Could not switch organization");
  return body as AuthUser;
}
