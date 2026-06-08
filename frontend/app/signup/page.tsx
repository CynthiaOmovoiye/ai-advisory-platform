"use client";

import { signIn } from "next-auth/react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";

export default function SignupPage() {
  const router = useRouter();
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [organizationName, setOrganizationName] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [pending, setPending] = useState(false);

  return (
    <form
      onSubmit={async (e) => {
        e.preventDefault();
        setPending(true);
        setError("");
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
          setError("Account created, but sign-in is waiting on email verification.");
          return;
        }
        router.push("/assessments");
      }}
      className="mx-auto max-w-md space-y-4 rounded-lg border bg-white p-6"
    >
      <h2 className="text-lg font-semibold">Create your account</h2>
      {error ? <p className="rounded-md bg-red-50 p-3 text-sm text-red-700">{error}</p> : null}
      <input
        type="text"
        placeholder="Name"
        value={name}
        onChange={(e) => setName(e.target.value)}
        className="w-full rounded-md border px-3 py-2 text-sm"
      />
      <input
        type="email"
        required
        placeholder="Email"
        value={email}
        onChange={(e) => setEmail(e.target.value)}
        className="w-full rounded-md border px-3 py-2 text-sm"
      />
      <input
        type="text"
        required
        placeholder="Organization name"
        value={organizationName}
        onChange={(e) => setOrganizationName(e.target.value)}
        className="w-full rounded-md border px-3 py-2 text-sm"
      />
      <input
        type="password"
        required
        minLength={12}
        placeholder="Password"
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
        {pending ? "Creating account..." : "Sign up"}
      </button>
      <p className="text-center text-sm text-slate-600">
        Already have an account?{" "}
        <Link href="/login" className="font-medium text-slate-900 hover:text-slate-700">
          Sign in
        </Link>
      </p>
    </form>
  );
}
