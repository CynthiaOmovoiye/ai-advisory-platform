import { NextResponse } from "next/server";

import { resetPassword } from "@/lib/backend-auth";

export async function POST(req: Request) {
  try {
    const { token, password } = (await req.json()) as { token: string; password: string };
    const result = await resetPassword(token, password);
    return NextResponse.json(result);
  } catch (e) {
    return NextResponse.json(
      { error: e instanceof Error ? e.message : "Password reset failed" },
      { status: 400 },
    );
  }
}
