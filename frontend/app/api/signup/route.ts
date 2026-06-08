import { NextResponse } from "next/server";

import { signupWithCredentials, verifyEmail } from "@/lib/backend-auth";

export async function POST(req: Request) {
  try {
    const body = (await req.json()) as {
      email: string;
      password: string;
      name?: string;
      organization_name: string;
    };
    const result = await signupWithCredentials(body);
    if (result.verification_token) {
      await verifyEmail(result.verification_token);
    }
    return NextResponse.json({ ok: true, email: result.user.email }, { status: 201 });
  } catch (e) {
    return NextResponse.json(
      { error: e instanceof Error ? e.message : "Signup failed" },
      { status: 400 },
    );
  }
}
