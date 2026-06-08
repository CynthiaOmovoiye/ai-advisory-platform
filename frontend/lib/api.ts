/**
 * Typed client for the FastAPI backend.
 *
 * Server-side only: it mints a BFF service token (ADR-0009) per request and sends it
 * as a bearer token to the API. Every response is validated with Zod before use, and
 * non-2xx responses surface the sanitized error envelope.
 */
import {
  AdminMetrics,
  ApiError,
  CompleteAssessmentResponse,
  EvaluationRun,
  EvaluationRunList,
  MemberList,
  type Member,
  InviteMemberResponse,
  OrganizationOut,
  type Organization,
  RecommendationList,
  RecommendationOut,
  ReportOut,
  type Recommendation,
} from "./schemas";
import { mintServiceToken, type SessionIdentity } from "./session-token";

export interface RecommendationPatch {
  title?: string;
  finding?: string;
  rationale?: string;
  remediation?: string;
  status?: "approved" | "rejected";
}

// Server-only: this client runs inside the BFF route handlers. Prefer a server var
// (API_BASE_URL, e.g. http://api:8000/v1 inside the Docker network) so it can be set
// at runtime; fall back to the public var, then localhost.
const BASE_URL =
  process.env.API_BASE_URL ?? process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000/v1";

export class ApiRequestError extends Error {
  constructor(
    public status: number,
    public code: string,
    public correlationId: string,
    message: string,
  ) {
    super(message);
    this.name = "ApiRequestError";
  }
}

async function request(
  identity: SessionIdentity,
  path: string,
  init: RequestInit = {},
): Promise<unknown> {
  const token = await mintServiceToken(identity);
  const res = await fetch(`${BASE_URL}${path}`, {
    ...init,
    headers: {
      ...init.headers,
      Authorization: `Bearer ${token}`,
      "Content-Type": "application/json",
    },
    cache: "no-store",
  });

  const body = await res.json().catch(() => null);
  if (!res.ok) {
    const parsed = ApiError.safeParse(body);
    if (parsed.success) {
      throw new ApiRequestError(res.status, parsed.data.code, parsed.data.correlationId, parsed.data.message);
    }
    throw new ApiRequestError(res.status, "unknown", "n/a", `Request failed (${res.status})`);
  }
  return body;
}

export async function completeAssessment(
  identity: SessionIdentity,
  assessmentId: string,
): Promise<CompleteAssessmentResponse> {
  const data = await request(identity, `/assessments/${assessmentId}/complete`, { method: "POST" });
  return CompleteAssessmentResponse.parse(data);
}

export async function listRecommendations(
  identity: SessionIdentity,
  assessmentId: string,
): Promise<Recommendation[]> {
  const data = await request(identity, `/assessments/${assessmentId}/recommendations`);
  return RecommendationList.parse(data);
}

export async function patchRecommendation(
  identity: SessionIdentity,
  recommendationId: string,
  patch: RecommendationPatch,
): Promise<Recommendation> {
  const data = await request(identity, `/recommendations/${recommendationId}`, {
    method: "PATCH",
    body: JSON.stringify(patch),
  });
  return RecommendationOut.parse(data);
}

export async function publishReport(
  identity: SessionIdentity,
  assessmentId: string,
): Promise<ReportOut> {
  const data = await request(identity, `/assessments/${assessmentId}/report`, { method: "POST" });
  return ReportOut.parse(data);
}

export async function getReport(
  identity: SessionIdentity,
  assessmentId: string,
): Promise<ReportOut | null> {
  try {
    return ReportOut.parse(await request(identity, `/assessments/${assessmentId}/report`));
  } catch (e) {
    if (e instanceof ApiRequestError && e.status === 404) return null;
    throw e;
  }
}

export async function getAdminMetrics(identity: SessionIdentity): Promise<AdminMetrics> {
  return AdminMetrics.parse(await request(identity, `/admin/metrics`));
}

export async function triggerEvaluation(identity: SessionIdentity): Promise<EvaluationRun> {
  const data = await request(identity, `/evaluation/runs`, { method: "POST", body: "{}" });
  return EvaluationRun.parse(data);
}

export async function listEvaluationRuns(identity: SessionIdentity): Promise<EvaluationRun[]> {
  return EvaluationRunList.parse(await request(identity, `/evaluation/runs`));
}


export async function listMembers(identity: SessionIdentity): Promise<Member[]> {
  return MemberList.parse(await request(identity, `/members`));
}

export async function inviteMember(
  identity: SessionIdentity,
  email: string,
  role: "org_user" | "consultant",
): Promise<{ member: Member; invite_token: string }> {
  return InviteMemberResponse.parse(
    await request(identity, `/members`, { method: "POST", body: JSON.stringify({ email, role }) }),
  );
}

export async function removeMember(identity: SessionIdentity, memberId: string): Promise<Member> {
  return MemberList.element.parse(await request(identity, `/members/${memberId}`, { method: "DELETE" }));
}

export async function createOrganization(
  identity: SessionIdentity,
  name: string,
  slug: string,
): Promise<Organization> {
  return OrganizationOut.parse(
    await request(identity, `/organizations`, { method: "POST", body: JSON.stringify({ name, slug }) }),
  );
}
