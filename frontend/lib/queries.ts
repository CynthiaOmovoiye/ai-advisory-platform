/**
 * React Query hooks (client-side).
 *
 * These call the same-origin BFF route handlers (not the backend directly), then
 * validate the payload with the same Zod schemas the server uses. The browser never
 * holds a backend token.
 */
"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import {
  AdminMetrics,
  CompleteAssessmentResponse,
  EvaluationRun,
  EvaluationRunList,
  MemberList,
  type Member,
  RecommendationList,
  RecommendationOut,
  ReportOut,
  type Recommendation,
} from "./schemas";

interface RecommendationPatch {
  title?: string;
  finding?: string;
  rationale?: string;
  remediation?: string;
  status?: "approved" | "rejected";
}

async function getJson(url: string, init?: RequestInit): Promise<unknown> {
  const res = await fetch(url, init);
  const body = await res.json().catch(() => null);
  if (!res.ok) {
    const message = (body && (body.message || body.error)) || `Request failed (${res.status})`;
    throw new Error(message);
  }
  return body;
}

export function useRecommendations(assessmentId: string) {
  return useQuery<Recommendation[]>({
    queryKey: ["recommendations", assessmentId],
    queryFn: async () => RecommendationList.parse(await getJson(`/api/assessments/${assessmentId}`)),
  });
}

export function useCompleteAssessment(assessmentId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async () => {
      const data = await getJson(`/api/assessments/${assessmentId}`, { method: "POST" });
      return CompleteAssessmentResponse.parse(data);
    },
    onSuccess: (data) => {
      // Seed the cache with the freshly produced recommendations.
      qc.setQueryData(["recommendations", assessmentId], data.recommendations);
    },
  });
}

export function usePatchRecommendation(assessmentId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (args: { id: string; patch: RecommendationPatch }) => {
      const data = await getJson(`/api/recommendations/${args.id}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(args.patch),
      });
      return RecommendationOut.parse(data);
    },
    onSuccess: () => qc.invalidateQueries({ queryKey: ["recommendations", assessmentId] }),
  });
}

export function usePublishReport(assessmentId: string) {
  return useMutation({
    mutationFn: async () =>
      ReportOut.parse(await getJson(`/api/assessments/${assessmentId}/report`, { method: "POST" })),
  });
}

export function useAdminMetrics() {
  return useQuery<AdminMetrics>({
    queryKey: ["admin-metrics"],
    queryFn: async () => AdminMetrics.parse(await getJson("/api/admin/metrics")),
  });
}

export function useEvaluationRuns() {
  return useQuery<EvaluationRun[]>({
    queryKey: ["evaluation-runs"],
    queryFn: async () => EvaluationRunList.parse(await getJson("/api/evaluation/runs")),
  });
}

export function useTriggerEvaluation() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async () =>
      EvaluationRun.parse(await getJson("/api/evaluation/runs", { method: "POST" })),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["evaluation-runs"] }),
  });
}


export function useMembers() {
  return useQuery<Member[]>({
    queryKey: ["members"],
    queryFn: async () => MemberList.parse(await getJson("/api/members")),
  });
}

export function useInviteMember() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (args: { email: string; role: "org_user" | "consultant" }) =>
      getJson("/api/members", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(args),
      }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["members"] }),
  });
}

export function useRemoveMember() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (id: string) => getJson(`/api/members/${id}`, { method: "DELETE" }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["members"] }),
  });
}
