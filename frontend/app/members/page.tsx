"use client";

import { useState } from "react";
import { UserPlus } from "lucide-react";

import { PageContainer, PageHeader } from "@/components/PageHeader";
import { StatusBadge } from "@/components/SeverityBadge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { selectClass } from "@/lib/utils";
import { useInviteMember, useMembers, useRemoveMember } from "@/lib/queries";

export default function MembersPage() {
  const members = useMembers();
  const invite = useInviteMember();
  const remove = useRemoveMember();
  const [email, setEmail] = useState("");
  const [role, setRole] = useState<"org_user" | "consultant">("org_user");

  return (
    <PageContainer>
      <PageHeader
        title="Organization members"
        description="Invite teammates and manage their roles within your organization."
      />

      <Card>
        <CardHeader>
          <CardTitle>Invite a member</CardTitle>
        </CardHeader>
        <CardContent>
          <form
            onSubmit={(e) => {
              e.preventDefault();
              invite.mutate({ email, role }, { onSuccess: () => setEmail("") });
            }}
            className="flex flex-wrap items-end gap-3"
          >
            <div className="flex-1 space-y-1.5">
              <Label htmlFor="m-email">Email</Label>
              <Input
                id="m-email"
                type="email"
                required
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="teammate@example.com"
              />
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="m-role">Role</Label>
              <select
                id="m-role"
                value={role}
                onChange={(e) => setRole(e.target.value as "org_user" | "consultant")}
                className={`${selectClass} w-40`}
              >
                <option value="org_user">Org user</option>
                <option value="consultant">Consultant</option>
              </select>
            </div>
            <Button type="submit" disabled={invite.isPending}>
              <UserPlus className="size-4" />
              {invite.isPending ? "Inviting…" : "Invite"}
            </Button>
          </form>
          {invite.isError && (
            <p className="mt-3 rounded-md bg-destructive/10 p-3 text-sm text-destructive">
              {(invite.error as Error).message}
            </p>
          )}
        </CardContent>
      </Card>

      <Card className="p-0">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b text-left text-xs uppercase tracking-wide text-muted-foreground">
              <th className="px-4 py-2.5 font-medium">Email</th>
              <th className="px-4 py-2.5 font-medium">Role</th>
              <th className="px-4 py-2.5 font-medium">Status</th>
              <th className="px-4 py-2.5"></th>
            </tr>
          </thead>
          <tbody className="divide-y">
            {(members.data ?? []).map((m) => (
              <tr key={m.id} className="hover:bg-accent/30">
                <td className="px-4 py-3">{m.invited_email}</td>
                <td className="px-4 py-3 capitalize text-muted-foreground">{m.role.replace(/_/g, " ")}</td>
                <td className="px-4 py-3">
                  <StatusBadge status={m.status} />
                </td>
                <td className="px-4 py-3 text-right">
                  {m.status !== "removed" && (
                    <Button
                      variant="ghost"
                      size="sm"
                      className="text-destructive hover:text-destructive"
                      onClick={() => remove.mutate(m.id)}
                    >
                      Remove
                    </Button>
                  )}
                </td>
              </tr>
            ))}
            {members.data?.length === 0 && (
              <tr>
                <td colSpan={4} className="px-4 py-10 text-center text-muted-foreground">
                  No members yet — invite someone above.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </Card>
    </PageContainer>
  );
}
