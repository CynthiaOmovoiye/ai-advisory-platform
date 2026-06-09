"use client";

import { signIn } from "next-auth/react";
import { useState } from "react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { CheckCircle2 } from "lucide-react";

import { AuthShell } from "@/components/AuthShell";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Suspense } from "react";

function LoginForm() {
  const router = useRouter();
  const params = useSearchParams();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [pending, setPending] = useState(false);

  const notice =
    params.get("reset") === "1"
      ? "Your password was reset. Sign in with your new password."
      : params.get("verified") === "1"
        ? "Email verified. You can sign in now."
        : "";

  return (
    <AuthShell
      title="Welcome back"
      description="Sign in to your AI Advisory workspace."
      footer={
        <>
          No account yet?{" "}
          <Link href="/signup" className="font-medium text-foreground underline-offset-4 hover:underline">
            Sign up
          </Link>
        </>
      }
    >
      <form
        onSubmit={async (e) => {
          e.preventDefault();
          setError("");
          setPending(true);
          const result = await signIn("credentials", { email, password, redirect: false });
          setPending(false);
          if (result?.error) {
            setError("Invalid email or password, or the account still needs email verification.");
            return;
          }
          router.push("/assessments");
        }}
        className="space-y-4"
      >
        {notice && (
          <p className="flex items-center gap-2 rounded-md bg-success/10 p-3 text-sm text-foreground">
            <CheckCircle2 className="size-4 text-success" /> {notice}
          </p>
        )}
        {error && (
          <p className="rounded-md bg-destructive/10 p-3 text-sm text-destructive">{error}</p>
        )}
        <div className="space-y-2">
          <Label htmlFor="email">Email</Label>
          <Input id="email" type="email" required value={email} onChange={(e) => setEmail(e.target.value)} placeholder="you@company.com" />
        </div>
        <div className="space-y-2">
          <div className="flex items-center justify-between">
            <Label htmlFor="password">Password</Label>
            <Link href="/forgot-password" className="text-xs text-muted-foreground underline-offset-4 hover:underline">
              Forgot password?
            </Link>
          </div>
          <Input id="password" type="password" required value={password} onChange={(e) => setPassword(e.target.value)} />
        </div>
        <Button type="submit" disabled={pending} className="w-full">
          {pending ? "Signing in…" : "Sign in"}
        </Button>
      </form>
    </AuthShell>
  );
}

export default function LoginPage() {
  return (
    <Suspense fallback={null}>
      <LoginForm />
    </Suspense>
  );
}
