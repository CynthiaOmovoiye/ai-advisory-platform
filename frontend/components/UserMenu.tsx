"use client";

import { signOut, useSession } from "next-auth/react";

export function UserMenu() {
  const { data: session, update } = useSession();
  if (!session?.user) {
    return (
      <div className="ml-auto flex gap-3 text-sm">
        <a href="/login" className="text-slate-600 hover:text-slate-900">Sign in</a>
        <a href="/signup" className="font-medium text-slate-900 hover:text-slate-700">Sign up</a>
      </div>
    );
  }

  return (
    <div className="ml-auto flex items-center gap-3 text-sm">
      {session.memberships && session.memberships.length > 1 ? (
        <select
          value={session.org}
          onChange={(e) => void update({ org: e.target.value })}
          className="rounded-md border px-2 py-1 text-sm"
          aria-label="Active organization"
        >
          {session.memberships.map((m) => (
            <option key={m.organization_id} value={m.organization_id}>
              {m.organization_name}
            </option>
          ))}
        </select>
      ) : (
        <span className="text-slate-500">
          {session.memberships?.[0]?.organization_name ?? session.org}
        </span>
      )}
      <span className="text-slate-600">{session.user.email}</span>
      <button
        type="button"
        onClick={() => void signOut({ callbackUrl: "/login" })}
        className="rounded-md border px-3 py-1.5 text-slate-700 hover:bg-slate-100"
      >
        Sign out
      </button>
    </div>
  );
}
