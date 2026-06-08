import { NextResponse } from "next/server";

import { requestPasswordReset } from "@/lib/backend-auth";

export async function POST(req: Request) {
  try {
    const { email } = (await req.json()) as { email: string };
    const result = await requestPasswordReset(email);
    return NextResponse.json(result);
  } catch {
    // Stay generic even on transport errors so this can't be used to probe for accounts.
    return NextResponse.json(
      { message: "If an account exists for that email, a password reset link has been sent." },
      { status: 200 },
    );
  }
}
