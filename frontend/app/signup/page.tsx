"use client";

import { signIn } from "next-auth/react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";

import { AuthShell } from "@/components/AuthShell";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";

export default function SignupPage() {
  const router = useRouter();
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [organizationName, setOrganizationName] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [pending, setPending] = useState(false);

  return (
    <AuthShell
      title="Create your account"
      description="Start a new organization and run your first assessment."
      footer={
        <>
          Already have an account?{" "}
          <Link href="/login" className="font-medium text-foreground underline-offset-4 hover:underline">
            Sign in
          </Link>
        </>
      }
    >
      <form
        onSubmit={async (e) => {
          e.preventDefault();
          setPending(true);
          setError("");
          setNotice("");
          const res = await fetch("/api/signup", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ name, email, password, organization_name: organizationName }),
          });
          const body = await res.json().catch(() => null);
          if (!res.ok) {
            setPending(false);
            setError(body?.error || "Could not create account.");
            return;
          }
          const result = await signIn("credentials", { email, password, redirect: false });
          setPending(false);
          if (result?.error) {
            setNotice("Account created. Check your email to verify your address, then sign in.");
            return;
          }
          router.push("/assessments");
        }}
        className="space-y-4"
      >
        {error && <p className="rounded-md bg-destructive/10 p-3 text-sm text-destructive">{error}</p>}
        {notice && <p className="rounded-md bg-success/10 p-3 text-sm text-foreground">{notice}</p>}
        <div className="space-y-2">
          <Label htmlFor="name">Name</Label>
          <Input id="name" value={name} onChange={(e) => setName(e.target.value)} placeholder="Ada Lovelace" />
        </div>
        <div className="space-y-2">
          <Label htmlFor="email">Email</Label>
          <Input id="email" type="email" required value={email} onChange={(e) => setEmail(e.target.value)} placeholder="you@company.com" />
        </div>
        <div className="space-y-2">
          <Label htmlFor="org">Organization name</Label>
          <Input id="org" required value={organizationName} onChange={(e) => setOrganizationName(e.target.value)} placeholder="Acme Advisory" />
        </div>
        <div className="space-y-2">
          <Label htmlFor="password">Password</Label>
          <Input id="password" type="password" required minLength={12} value={password} onChange={(e) => setPassword(e.target.value)} />
          <p className="text-xs text-muted-foreground">
            At least 12 characters with uppercase, lowercase, a number, and a symbol.
          </p>
        </div>
        <Button type="submit" disabled={pending} className="w-full">
          {pending ? "Creating account…" : "Create account"}
        </Button>
      </form>
    </AuthShell>
  );
}
