/**
 * Zod schemas mirroring the backend API DTOs (docs/api/openapi.yaml).
 *
 * Every response from the FastAPI backend is parsed through these before it is used,
 * so the boundary is validated at runtime, not just typed at compile time. Types are
 * derived from the schemas (single source of truth).
 */
import { z } from "zod";

export const Severity = z.enum(["info", "low", "medium", "high", "critical"]);
export type Severity = z.infer<typeof Severity>;

export const Provenance = z.object({
  source: z.enum(["llm", "fallback"]),
  grounding_passed: z.boolean().nullable(),
});

export const RecommendationStatus = z.enum(["draft", "edited", "approved", "rejected"]);
export type RecommendationStatus = z.infer<typeof RecommendationStatus>;

export const RecommendationOut = z.object({
  id: z.string().nullable(),
  rule_code: z.string(),
  category: z.string(),
  severity: Severity,
  title: z.string(),
  finding: z.string(),
  rationale: z.string(),
  remediation: z.string(),
  status: RecommendationStatus,
  provenance: Provenance,
});
export type Recommendation = z.infer<typeof RecommendationOut>;

export const ReportOut = z.object({
  id: z.string(),
  assessment_id: z.string(),
  title: z.string(),
  status: z.string(),
  pdf_url: z.string().nullable(),
});
export type ReportOut = z.infer<typeof ReportOut>;

export const AdminMetrics = z.object({
  organizations: z.number(),
  assessments_total: z.number(),
  assessments_by_status: z.record(z.string(), z.number()),
  reports_published: z.number(),
  ai_usage: z.object({
    recommendations_total: z.number(),
    by_source: z.record(z.string(), z.number()),
    grounding_pass_rate: z.number().nullable(),
  }),
  evaluation: z.object({
    latest_accuracy: z.number().nullable(),
    latest_hallucination_rate: z.number().nullable(),
    latest_status: z.string().nullable(),
  }),
});
export type AdminMetrics = z.infer<typeof AdminMetrics>;

export const EvaluationRun = z.object({
  id: z.string(),
  dataset_name: z.string(),
  ruleset_name: z.string(),
  model_id: z.string(),
  status: z.string(),
  accuracy: z.number(),
  consistency: z.number(),
  completeness: z.number(),
  hallucination_rate: z.number(),
  item_count: z.number(),
});
export type EvaluationRun = z.infer<typeof EvaluationRun>;
export const EvaluationRunList = z.array(EvaluationRun);

export const CompleteAssessmentResponse = z.object({
  assessment_id: z.string(),
  status: z.string(),
  recommendations: z.array(RecommendationOut),
});
export type CompleteAssessmentResponse = z.infer<typeof CompleteAssessmentResponse>;

export const RecommendationList = z.array(RecommendationOut);

export const MemberOut = z.object({
  id: z.string(),
  invited_email: z.string(),
  role: z.string(),
  status: z.string(),
});
export type Member = z.infer<typeof MemberOut>;
export const MemberList = z.array(MemberOut);

export const InviteMemberResponse = z.object({
  member: MemberOut,
  invite_token: z.string(),
});
export type InviteMemberResponse = z.infer<typeof InviteMemberResponse>;

export const OrganizationOut = z.object({
  id: z.string(),
  name: z.string(),
  slug: z.string(),
});
export type Organization = z.infer<typeof OrganizationOut>;

/** Sanitized error envelope (matches the backend `Error` schema). */
export const ApiError = z.object({
  code: z.string(),
  message: z.string(),
  correlationId: z.string(),
});
export type ApiError = z.infer<typeof ApiError>;
