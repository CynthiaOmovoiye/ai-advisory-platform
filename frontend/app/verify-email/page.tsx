"use client";

import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { Suspense, useEffect, useState } from "react";

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
    <div className="mx-auto max-w-sm space-y-4 rounded-lg border bg-white p-6 text-center">
      {status === "pending" && <p className="text-sm text-slate-600">Verifying your email…</p>}
      {status === "ok" && (
        <>
          <h2 className="text-lg font-semibold">Email verified</h2>
          <p className="text-sm text-slate-600">Your account is now active.</p>
          <Link
            href="/login"
            className="inline-block rounded-md bg-slate-900 px-4 py-2 text-sm font-medium text-white hover:bg-slate-700"
          >
            Sign in
          </Link>
        </>
      )}
      {status === "error" && (
        <>
          <h2 className="text-lg font-semibold">Verification failed</h2>
          <p className="text-sm text-slate-600">
            This link is invalid or has expired. Try signing in to request a new one.
          </p>
          <Link href="/login" className="text-sm font-medium text-slate-900 hover:text-slate-700">
            Go to sign in
          </Link>
        </>
      )}
    </div>
  );
}

export default function VerifyEmailPage() {
  return (
    <Suspense fallback={null}>
      <VerifyEmail />
    </Suspense>
  );
}
