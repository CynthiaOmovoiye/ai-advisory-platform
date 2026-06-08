"use client";

import { signIn } from "next-auth/react";
import { useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";

export default function LoginPage() {
  const router = useRouter();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [pending, setPending] = useState(false);

  return (
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
      className="mx-auto max-w-sm space-y-4 rounded-lg border bg-white p-6"
    >
      <h2 className="text-lg font-semibold">Sign in</h2>
      {error ? <p className="rounded-md bg-red-50 p-3 text-sm text-red-700">{error}</p> : null}
      <input
        type="email"
        required
        placeholder="Email"
        value={email}
        onChange={(e) => setEmail(e.target.value)}
        className="w-full rounded-md border px-3 py-2 text-sm"
      />
      <input
        type="password"
        required
        placeholder="Password"
        value={password}
        onChange={(e) => setPassword(e.target.value)}
        className="w-full rounded-md border px-3 py-2 text-sm"
      />
      <button
        type="submit"
        disabled={pending}
        className="w-full rounded-md bg-slate-900 px-4 py-2 text-sm font-medium text-white hover:bg-slate-700"
      >
        {pending ? "Signing in..." : "Sign in"}
      </button>
      <p className="text-center text-sm text-slate-600">
        No account yet?{" "}
        <Link href="/signup" className="font-medium text-slate-900 hover:text-slate-700">
          Sign up
        </Link>
      </p>
      <p className="text-center text-sm text-slate-600">
        <Link href="/forgot-password" className="font-medium text-slate-900 hover:text-slate-700">
          Forgot your password?
        </Link>
      </p>
    </form>
  );
}
