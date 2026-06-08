"use client";

import { use } from "react";

import { SeverityBadge } from "@/components/SeverityBadge";
import { useQueryClient } from "@tanstack/react-query";

import {
  useCompleteAssessment,
  usePatchRecommendation,
  usePublishReport,
  useRecommendations,
  useReport,
} from "@/lib/queries";
import type { Recommendation } from "@/lib/schemas";

export default function AssessmentDetail({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params);
  const qc = useQueryClient();
  const recommendations = useRecommendations(id);
  const complete = useCompleteAssessment(id);
  const patch = usePatchRecommendation(id);
  const publish = usePublishReport(id);
  const report = useReport(id, true); // polls queued -> published

  const recs = recommendations.data ?? [];
  const allReviewed = recs.length > 0 && recs.every((r) => r.status === "approved" || r.status === "rejected");

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h2 className="text-xl font-semibold">Assessment {id}</h2>
        <div className="flex gap-2">
          <button
            onClick={() => complete.mutate()}
            disabled={complete.isPending}
            className="rounded-md bg-slate-900 px-4 py-2 text-sm font-medium text-white hover:bg-slate-700 disabled:opacity-50"
          >
            {complete.isPending ? "Evaluating…" : "Complete & generate findings"}
          </button>
          <button
            onClick={() =>
              publish.mutate(undefined, {
                onSuccess: () => qc.invalidateQueries({ queryKey: ["report", id] }),
              })
            }
            disabled={!allReviewed || publish.isPending}
            title={allReviewed ? "" : "Approve or reject every recommendation first"}
            className="rounded-md border border-slate-900 px-4 py-2 text-sm font-medium text-slate-900 hover:bg-slate-100 disabled:opacity-40"
          >
            {publish.isPending ? "Requesting…" : "Publish report"}
          </button>
        </div>
      </div>

      {report.data?.status === "queued" && (
        <p className="rounded-md bg-amber-50 p-3 text-sm text-amber-800">
          Report rendering in the background…
        </p>
      )}
      {report.data?.status === "published" && report.data.pdf_url && (
        <a
          href={report.data.pdf_url}
          className="block rounded-md bg-green-50 p-3 text-sm text-green-800"
        >
          Report published — view PDF
        </a>
      )}
      {[complete.error, patch.error, publish.error].filter(Boolean).map((e, i) => (
        <p key={i} className="rounded-md bg-red-50 p-3 text-sm text-red-700">
          {(e as Error).message}
        </p>
      ))}

      {recommendations.isLoading && <p className="text-slate-500">Loading…</p>}

      <div className="space-y-3">
        {recs.length === 0 && (
          <p className="text-slate-500">No findings yet — complete the assessment to generate them.</p>
        )}
        {recs.map((rec) => (
          <WorkspaceCard
            key={rec.id ?? rec.rule_code}
            rec={rec}
            onApprove={() => rec.id && patch.mutate({ id: rec.id, patch: { status: "approved" } })}
            onReject={() => rec.id && patch.mutate({ id: rec.id, patch: { status: "rejected" } })}
            busy={patch.isPending}
          />
        ))}
      </div>
    </div>
  );
}

function WorkspaceCard({
  rec,
  onApprove,
  onReject,
  busy,
}: {
  rec: Recommendation;
  onApprove: () => void;
  onReject: () => void;
  busy: boolean;
}) {
  return (
    <article className="rounded-lg border bg-white p-4 shadow-sm">
      <div className="flex items-center gap-2">
        <SeverityBadge severity={rec.severity} />
        <span className="text-xs text-slate-500">{rec.rule_code}</span>
        <span className="ml-auto rounded bg-slate-100 px-2 py-0.5 text-xs font-medium text-slate-600">
          {rec.status}
        </span>
      </div>
      <h3 className="mt-2 font-semibold">{rec.title}</h3>
      <p className="mt-1 text-sm text-slate-700">
        <span className="font-medium text-slate-500">Rationale: </span>
        {rec.rationale}
      </p>
      <p className="mt-1 text-sm text-slate-700">
        <span className="font-medium text-slate-500">Remediation: </span>
        {rec.remediation}
      </p>
      <div className="mt-3 flex gap-2">
        <button
          onClick={onApprove}
          disabled={busy || rec.status === "approved"}
          className="rounded-md bg-green-600 px-3 py-1 text-xs font-medium text-white hover:bg-green-700 disabled:opacity-40"
        >
          Approve
        </button>
        <button
          onClick={onReject}
          disabled={busy || rec.status === "rejected"}
          className="rounded-md bg-red-600 px-3 py-1 text-xs font-medium text-white hover:bg-red-700 disabled:opacity-40"
        >
          Reject
        </button>
      </div>
    </article>
  );
}
