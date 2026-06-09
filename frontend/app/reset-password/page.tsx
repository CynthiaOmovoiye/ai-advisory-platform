"use client";

import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { Suspense, useState } from "react";

import { AuthShell } from "@/components/AuthShell";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";

function ResetPasswordForm() {
  const router = useRouter();
  const token = useSearchParams().get("token") ?? "";
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [pending, setPending] = useState(false);

  if (!token) {
    return (
      <AuthShell
        title="Invalid reset link"
        description="This link is missing its token. Request a new one from the sign-in page."
        footer={
          <Link href="/forgot-password" className="font-medium text-foreground underline-offset-4 hover:underline">
            Request a new link
          </Link>
        }
      >
        <Link href="/forgot-password" className="text-sm text-muted-foreground underline-offset-4 hover:underline">
          Request a new reset link →
        </Link>
      </AuthShell>
    );
  }

  return (
    <AuthShell title="Choose a new password" description="Set a strong password for your account.">
      <form
        onSubmit={async (e) => {
          e.preventDefault();
          setPending(true);
          setError("");
          const res = await fetch("/api/reset-password", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ token, password }),
          });
          const body = await res.json().catch(() => null);
          setPending(false);
          if (!res.ok) {
            setError(body?.error || "This reset link is invalid or has expired.");
            return;
          }
          router.push("/login?reset=1");
        }}
        className="space-y-4"
      >
        {error && <p className="rounded-md bg-destructive/10 p-3 text-sm text-destructive">{error}</p>}
        <div className="space-y-2">
          <Label htmlFor="password">New password</Label>
          <Input id="password" type="password" required minLength={12} value={password} onChange={(e) => setPassword(e.target.value)} />
          <p className="text-xs text-muted-foreground">
            At least 12 characters with uppercase, lowercase, a number, and a symbol.
          </p>
        </div>
        <Button type="submit" disabled={pending} className="w-full">
          {pending ? "Updating…" : "Reset password"}
        </Button>
      </form>
    </AuthShell>
  );
}

export default function ResetPasswordPage() {
  return (
    <Suspense fallback={null}>
      <ResetPasswordForm />
    </Suspense>
  );
}
