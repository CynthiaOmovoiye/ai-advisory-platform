/**
 * Auth.js (NextAuth v5) configuration.
 *
 * Owns the user session. After authentication, the user's id, active organization,
 * and roles are carried on the session; `getSessionIdentity()` projects them into the
 * narrow shape the BFF token (ADR-0009) needs. In production you would swap the demo
 * Credentials provider for a real IdP — nothing downstream changes.
 */
import NextAuth, { type DefaultSession } from "next-auth";
import Credentials from "next-auth/providers/credentials";

import type { SessionIdentity } from "./session-token";

declare module "next-auth" {
  interface Session {
    org?: string;
    globalRoles?: string[];
    orgRoles?: Record<string, string[]>;
    user: { id: string } & DefaultSession["user"];
  }
}

export const { handlers, auth, signIn, signOut } = NextAuth({
  session: { strategy: "jwt" },
  providers: [
    Credentials({
      // Demo provider. Replace with a real IdP; the contract below is what matters.
      credentials: { email: {}, password: {} },
      async authorize(creds) {
        if (!creds?.email) return null;
        // A real provider verifies the password and loads roles/org from the backend.
        return {
          id: "demo-user",
          email: String(creds.email),
          name: "Demo User",
          org: "demo-org",
          orgRoles: { "demo-org": ["org_user"] },
        } as unknown as { id: string };
      },
    }),
  ],
  callbacks: {
    async jwt({ token, user }) {
      if (user) {
        const u = user as Record<string, unknown>;
        token.org = u.org;
        token.orgRoles = u.orgRoles;
        token.globalRoles = u.globalRoles;
      }
      return token;
    },
    async session({ session, token }) {
      session.user.id = String(token.sub);
      session.org = token.org as string | undefined;
      session.orgRoles = token.orgRoles as Record<string, string[]> | undefined;
      session.globalRoles = token.globalRoles as string[] | undefined;
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
  };
}
