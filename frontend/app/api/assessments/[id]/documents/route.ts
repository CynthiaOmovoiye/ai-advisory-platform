/**
 * BFF document upload — forwards the multipart file to the backend with the minted
 * service token. The backend validates (ext/MIME/magic/size) and enqueues the scan.
 */
import { NextResponse } from "next/server";

import { getSessionIdentity } from "@/lib/auth";
import { mintServiceToken } from "@/lib/session-token";

const BASE_URL =
  process.env.API_BASE_URL ?? process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000/v1";

export async function POST(req: Request, { params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  const identity = await getSessionIdentity();
  if (!identity) return NextResponse.json({ error: "unauthenticated" }, { status: 401 });

  const token = await mintServiceToken(identity);
  const form = await req.formData(); // re-forward the uploaded file as-is
  const res = await fetch(`${BASE_URL}/assessments/${id}/documents`, {
    method: "POST",
    headers: { Authorization: `Bearer ${token}` },
    body: form,
  });
  const body = await res.json().catch(() => null);
  return NextResponse.json(body, { status: res.status });
}
