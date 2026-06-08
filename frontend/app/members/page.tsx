"use client";

import { useState } from "react";

import { useInviteMember, useMembers, useRemoveMember } from "@/lib/queries";

export default function MembersPage() {
  const members = useMembers();
  const invite = useInviteMember();
  const remove = useRemoveMember();
  const [email, setEmail] = useState("");
  const [role, setRole] = useState<"org_user" | "consultant">("org_user");

  return (
    <div className="space-y-6">
      <h2 className="text-xl font-semibold">Organization Members</h2>

      <form
        onSubmit={(e) => {
          e.preventDefault();
          invite.mutate({ email, role }, { onSuccess: () => setEmail("") });
        }}
        className="flex flex-wrap items-end gap-2 rounded-lg border bg-white p-4"
      >
        <div className="flex-1">
          <label className="block text-xs text-slate-500">Email</label>
          <input
            type="email"
            required
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            className="w-full rounded-md border px-3 py-2 text-sm"
            placeholder="teammate@example.com"
          />
        </div>
        <div>
          <label className="block text-xs text-slate-500">Role</label>
          <select
            value={role}
            onChange={(e) => setRole(e.target.value as "org_user" | "consultant")}
            className="rounded-md border px-3 py-2 text-sm"
          >
            <option value="org_user">Org user</option>
            <option value="consultant">Consultant</option>
          </select>
        </div>
        <button
          type="submit"
          disabled={invite.isPending}
          className="rounded-md bg-slate-900 px-4 py-2 text-sm font-medium text-white hover:bg-slate-700 disabled:opacity-50"
        >
          {invite.isPending ? "Inviting…" : "Invite"}
        </button>
      </form>

      {invite.isError && (
        <p className="rounded-md bg-red-50 p-3 text-sm text-red-700">
          {(invite.error as Error).message}
        </p>
      )}

      <div className="overflow-hidden rounded-lg border bg-white">
        <table className="w-full text-sm">
          <thead className="bg-slate-50 text-left text-xs uppercase text-slate-500">
            <tr>
              <th className="px-4 py-2">Email</th>
              <th className="px-4 py-2">Role</th>
              <th className="px-4 py-2">Status</th>
              <th className="px-4 py-2"></th>
            </tr>
          </thead>
          <tbody className="divide-y">
            {(members.data ?? []).map((m) => (
              <tr key={m.id}>
                <td className="px-4 py-2">{m.invited_email}</td>
                <td className="px-4 py-2">{m.role}</td>
                <td className="px-4 py-2">{m.status}</td>
                <td className="px-4 py-2 text-right">
                  {m.status !== "removed" && (
                    <button
                      onClick={() => remove.mutate(m.id)}
                      className="text-xs font-medium text-red-700 hover:underline"
                    >
                      Remove
                    </button>
                  )}
                </td>
              </tr>
            ))}
            {members.data?.length === 0 && (
              <tr>
                <td colSpan={4} className="px-4 py-6 text-center text-slate-500">
                  No members yet — invite someone above.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
