/**
 * Shared helpers for the BFF route handlers: resolve the session identity and
 * translate backend errors into JSON responses. Keeps each route handler thin.
 */
import { NextResponse } from "next/server";

import { ApiRequestError } from "./api";
import { getSessionIdentity } from "./auth";
import type { SessionIdentity } from "./session-token";

export async function withIdentity(
  fn: (identity: SessionIdentity) => Promise<unknown>,
): Promise<NextResponse> {
  const identity = await getSessionIdentity();
  if (!identity) {
    return NextResponse.json({ error: "unauthenticated" }, { status: 401 });
  }
  try {
    return NextResponse.json(await fn(identity));
  } catch (e) {
    if (e instanceof ApiRequestError) {
      return NextResponse.json({ error: e.code, message: e.message }, { status: e.status });
    }
    return NextResponse.json({ error: "internal_error" }, { status: 500 });
  }
}
