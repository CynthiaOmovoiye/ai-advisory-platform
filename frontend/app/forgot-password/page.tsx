"use client";

import Link from "next/link";
import { useState } from "react";
import { MailCheck } from "lucide-react";

import { AuthShell } from "@/components/AuthShell";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";

export default function ForgotPasswordPage() {
  const [email, setEmail] = useState("");
  const [message, setMessage] = useState("");
  const [pending, setPending] = useState(false);

  if (message) {
    return (
      <AuthShell
        title="Check your email"
        footer={
          <Link href="/login" className="font-medium text-foreground underline-offset-4 hover:underline">
            Back to sign in
          </Link>
        }
      >
        <div className="flex flex-col items-center gap-3 py-2 text-center">
          <span className="grid size-10 place-items-center rounded-full bg-success/10 text-success">
            <MailCheck className="size-5" />
          </span>
          <p className="text-sm text-muted-foreground">{message}</p>
        </div>
      </AuthShell>
    );
  }

  return (
    <AuthShell
      title="Reset your password"
      description="Enter your email and we'll send you a link to choose a new password."
      footer={
        <Link href="/login" className="font-medium text-foreground underline-offset-4 hover:underline">
          Back to sign in
        </Link>
      }
    >
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
          setMessage(
            body?.message ??
              "If an account exists for that email, a password reset link has been sent.",
          );
        }}
        className="space-y-4"
      >
        <div className="space-y-2">
          <Label htmlFor="email">Email</Label>
          <Input id="email" type="email" required value={email} onChange={(e) => setEmail(e.target.value)} placeholder="you@company.com" />
        </div>
        <Button type="submit" disabled={pending} className="w-full">
          {pending ? "Sending…" : "Send reset link"}
        </Button>
      </form>
    </AuthShell>
  );
}
