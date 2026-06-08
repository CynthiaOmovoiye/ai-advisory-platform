import { NextResponse } from "next/server";

import { verifyEmail } from "@/lib/backend-auth";

export async function POST(req: Request) {
  try {
    const { token } = (await req.json()) as { token: string };
    await verifyEmail(token);
    return NextResponse.json({ ok: true });
  } catch (e) {
    return NextResponse.json(
      { error: e instanceof Error ? e.message : "Verification failed" },
      { status: 400 },
    );
  }
}
