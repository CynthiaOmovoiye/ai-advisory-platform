"use client";

import Link from "next/link";
import { useState } from "react";

export default function ForgotPasswordPage() {
  const [email, setEmail] = useState("");
  const [message, setMessage] = useState("");
  const [pending, setPending] = useState(false);

  if (message) {
    return (
      <div className="mx-auto max-w-sm space-y-4 rounded-lg border bg-white p-6">
        <h2 className="text-lg font-semibold">Check your email</h2>
        <p className="text-sm text-slate-600">{message}</p>
        <Link href="/login" className="text-sm font-medium text-slate-900 hover:text-slate-700">
          Back to sign in
        </Link>
      </div>
    );
  }

  return (
    <form
      onSubmit={async (e) => {
        e.preventDefault();
        setPending(true);
        const res = await fetch("/api/forgot-password", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ email }),
        });
        const body = await res.json().catch(() => null);
        setPending(false);
        // Always show the same generic confirmation — no account enumeration.
        setMessage(
          body?.message ??
            "If an account exists for that email, a password reset link has been sent.",
        );
      }}
      className="mx-auto max-w-sm space-y-4 rounded-lg border bg-white p-6"
    >
      <h2 className="text-lg font-semibold">Reset your password</h2>
      <p className="text-sm text-slate-600">
        Enter your email and we&apos;ll send you a link to choose a new password.
      </p>
      <input
        type="email"
        required
        placeholder="Email"
        value={email}
        onChange={(e) => setEmail(e.target.value)}
        className="w-full rounded-md border px-3 py-2 text-sm"
      />
      <button
        type="submit"
        disabled={pending}
        className="w-full rounded-md bg-slate-900 px-4 py-2 text-sm font-medium text-white hover:bg-slate-700 disabled:opacity-60"
      >
        {pending ? "Sending..." : "Send reset link"}
      </button>
      <p className="text-center text-sm text-slate-600">
        <Link href="/login" className="font-medium text-slate-900 hover:text-slate-700">
          Back to sign in
        </Link>
      </p>
    </form>
  );
}
