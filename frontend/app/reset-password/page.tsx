"use client";

import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { Suspense, useState } from "react";

function ResetPasswordForm() {
  const router = useRouter();
  const token = useSearchParams().get("token") ?? "";
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [pending, setPending] = useState(false);

  if (!token) {
    return (
      <div className="mx-auto max-w-sm space-y-4 rounded-lg border bg-white p-6">
        <h2 className="text-lg font-semibold">Invalid reset link</h2>
        <p className="text-sm text-slate-600">
          This link is missing its token. Request a new one from the sign-in page.
        </p>
        <Link href="/forgot-password" className="text-sm font-medium text-slate-900">
          Request a new link
        </Link>
      </div>
    );
  }

  return (
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
      className="mx-auto max-w-sm space-y-4 rounded-lg border bg-white p-6"
    >
      <h2 className="text-lg font-semibold">Choose a new password</h2>
      {error ? <p className="rounded-md bg-red-50 p-3 text-sm text-red-700">{error}</p> : null}
      <input
        type="password"
        required
        minLength={12}
        placeholder="New password"
        value={password}
        onChange={(e) => setPassword(e.target.value)}
        className="w-full rounded-md border px-3 py-2 text-sm"
      />
      <p className="text-xs text-slate-500">
        Use at least 12 characters with uppercase, lowercase, a number, and a symbol.
      </p>
      <button
        type="submit"
        disabled={pending}
        className="w-full rounded-md bg-slate-900 px-4 py-2 text-sm font-medium text-white hover:bg-slate-700 disabled:opacity-60"
      >
        {pending ? "Updating..." : "Reset password"}
      </button>
    </form>
  );
}

export default function ResetPasswordPage() {
  return (
    <Suspense fallback={null}>
      <ResetPasswordForm />
    </Suspense>
  );
}
