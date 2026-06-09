"use client";

import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { Suspense, useEffect, useState } from "react";
import { CheckCircle2, Loader2, XCircle } from "lucide-react";

import { AuthShell } from "@/components/AuthShell";
import { buttonVariants } from "@/components/ui/button";

type Status = "pending" | "ok" | "error";

function VerifyEmail() {
  const token = useSearchParams().get("token") ?? "";
  const [status, setStatus] = useState<Status>("pending");

  useEffect(() => {
    if (!token) {
      setStatus("error");
      return;
    }
    let cancelled = false;
    (async () => {
      const res = await fetch("/api/verify-email", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ token }),
      });
      if (!cancelled) setStatus(res.ok ? "ok" : "error");
    })();
    return () => {
      cancelled = true;
    };
  }, [token]);

  return (
    <AuthShell title="Email verification">
      <div className="flex flex-col items-center gap-4 py-2 text-center">
        {status === "pending" && (
          <>
            <Loader2 className="size-8 animate-spin text-muted-foreground" />
            <p className="text-sm text-muted-foreground">Verifying your email…</p>
          </>
        )}
        {status === "ok" && (
          <>
            <span className="grid size-12 place-items-center rounded-full bg-success/10 text-success">
              <CheckCircle2 className="size-6" />
            </span>
            <p className="text-sm text-muted-foreground">Your account is now active.</p>
            <Link href="/login?verified=1" className={buttonVariants({ className: "w-full" })}>
              Continue to sign in
            </Link>
          </>
        )}
        {status === "error" && (
          <>
            <span className="grid size-12 place-items-center rounded-full bg-destructive/10 text-destructive">
              <XCircle className="size-6" />
            </span>
            <p className="text-sm text-muted-foreground">
              This link is invalid or has expired. Try signing in to request a new one.
            </p>
            <Link href="/login" className={buttonVariants({ variant: "outline", className: "w-full" })}>
              Go to sign in
            </Link>
          </>
        )}
      </div>
    </AuthShell>
  );
}

export default function VerifyEmailPage() {
  return (
    <Suspense fallback={null}>
      <VerifyEmail />
    </Suspense>
  );
}
