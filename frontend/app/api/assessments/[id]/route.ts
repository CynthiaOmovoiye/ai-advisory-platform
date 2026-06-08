/**
 * BFF route handlers for an assessment.
 *
 * The browser talks to these (same-origin); they resolve the session, mint the
 * service token, and call the FastAPI backend. The backend token never reaches the
 * client — this is the BFF boundary (ADR-0009).
 */
import { NextResponse } from "next/server";

import { ApiRequestError, completeAssessment, listRecommendations } from "@/lib/api";
import { getSessionIdentity } from "@/lib/auth";

async function requireIdentity() {
  const identity = await getSessionIdentity();
  if (!identity) {
    return { error: NextResponse.json({ error: "unauthenticated" }, { status: 401 }) };
  }
  return { identity };
}

export async function GET(_req: Request, { params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  const { identity, error } = await requireIdentity();
  if (error) return error;
  try {
    const recs = await listRecommendations(identity!, id);
    return NextResponse.json(recs);
  } catch (e) {
    return errorResponse(e);
  }
}

export async function POST(_req: Request, { params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  const { identity, error } = await requireIdentity();
  if (error) return error;
  try {
    const result = await completeAssessment(identity!, id);
    return NextResponse.json(result, { status: 202 });
  } catch (e) {
    return errorResponse(e);
  }
}

function errorResponse(e: unknown) {
  if (e instanceof ApiRequestError) {
    return NextResponse.json({ error: e.code, message: e.message }, { status: e.status });
  }
  return NextResponse.json({ error: "internal_error" }, { status: 500 });
}
