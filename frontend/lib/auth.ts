/**
 * Auth.js (NextAuth v5) configuration.
 *
 * Owns the user session. After authentication, the user's id, active organization,
 * and roles are carried on the session; `getSessionIdentity()` projects them into the
 * narrow shape the BFF token (ADR-0009) needs. In production you would swap the demo
 */
import NextAuth, { type DefaultSession } from "next-auth";
import Credentials from "next-auth/providers/credentials";

import { signinWithCredentials, switchActiveOrganization, type AuthMembership } from "./backend-auth";
import type { SessionIdentity } from "./session-token";

declare module "next-auth" {
  interface Session {
    org?: string;
    globalRoles?: string[];
    orgRoles?: Record<string, string[]>;
    memberships?: AuthMembership[];
    sessionVersion?: number;
    user: { id: string } & DefaultSession["user"];
  }
}

const credentialsProvider = Credentials({
  credentials: { email: {}, password: {} },
  async authorize(creds) {
    if (!creds?.email || !creds?.password) return null;
    try {
      const user = await signinWithCredentials(String(creds.email), String(creds.password));
      return {
        id: user.id,
        email: user.email,
        name: user.name ?? user.email,
        org: user.active_org,
        globalRoles: user.global_roles,
        orgRoles: user.org_roles,
        memberships: user.memberships,
        sessionVersion: user.session_version,
      } as unknown as { id: string };
    } catch {
      return null;
    }
  },
});

export const { handlers, auth, signIn, signOut } = NextAuth({
  session: { strategy: "jwt" },
  providers: [credentialsProvider],
  callbacks: {
    async jwt({ token, user, trigger, session }) {
      if (user) {
        const u = user as Record<string, unknown>;
        token.org = u.org;
        token.orgRoles = u.orgRoles;
        token.globalRoles = u.globalRoles;
        token.memberships = u.memberships;
        token.sessionVersion = u.sessionVersion;
      }
      if (trigger === "update" && session?.org && token.sub && token.org) {
        const profile = await switchActiveOrganization(
          {
            userId: String(token.sub),
            activeOrg: String(token.org),
            globalRoles: (token.globalRoles as string[] | undefined) ?? [],
            orgRoles: (token.orgRoles as Record<string, string[]> | undefined) ?? {},
          },
          String(session.org),
        );
        token.org = profile.active_org;
        token.orgRoles = profile.org_roles;
        token.globalRoles = profile.global_roles;
        token.memberships = profile.memberships;
        token.sessionVersion = profile.session_version;
      }
      return token;
    },
    async session({ session, token }) {
      session.user.id = String(token.sub);
      session.org = token.org as string | undefined;
      session.orgRoles = token.orgRoles as Record<string, string[]> | undefined;
      session.globalRoles = token.globalRoles as string[] | undefined;
      session.memberships = token.memberships as AuthMembership[] | undefined;
      session.sessionVersion = token.sessionVersion as number | undefined;
      return session;
    },
  },
});

export async function getSessionIdentity(): Promise<SessionIdentity | null> {
  const session = await auth();
  if (!session?.user?.id || !session.org) return null;
  return {
    userId: session.user.id,
    activeOrg: session.org,
    globalRoles: session.globalRoles,
    orgRoles: session.orgRoles,
    sessionVersion: session.sessionVersion,
  };
}
