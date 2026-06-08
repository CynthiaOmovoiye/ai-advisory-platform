"use client";

import { useQueryClient } from "@tanstack/react-query";
import { use, useState } from "react";

import { QuestionField } from "@/components/QuestionField";
import { SeverityBadge } from "@/components/SeverityBadge";
import {
  useAssessmentDetail,
  useCompleteAssessment,
  usePatchRecommendation,
  usePublishReport,
  useRecommendations,
  useReport,
  useSaveResponses,
} from "@/lib/queries";
import type { AssessmentDetail, Recommendation } from "@/lib/schemas";

export default function AssessmentDetailPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params);
  const detail = useAssessmentDetail(id);

  if (detail.isLoading) return <p className="text-slate-500">Loading…</p>;
  if (detail.isError)
    return <p className="rounded-md bg-red-50 p-3 text-sm text-red-700">{(detail.error as Error).message}</p>;

  const a = detail.data!;
  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h2 className="text-xl font-semibold">{a.template_name}</h2>
        <span className="rounded bg-slate-100 px-2 py-0.5 text-xs font-medium text-slate-600">{a.status}</span>
      </div>
      {a.status === "in_progress" ? <AnswerForm id={id} detail={a} /> : <ReviewView id={id} />}
    </div>
  );
}

function AnswerForm({ id, detail }: { id: string; detail: AssessmentDetail }) {
  const qc = useQueryClient();
  const save = useSaveResponses(id);
  const complete = useCompleteAssessment(id);
  const [answers, setAnswers] = useState<Record<string, unknown>>(detail.responses);
  const [errors, setErrors] = useState<string[]>([]);

  const allQuestions = detail.sections.flatMap((s) => s.questions);
  const toPairs = () =>
    Object.entries(answers)
      .filter(([, v]) => v !== undefined && v !== null && v !== "")
      .map(([key, value]) => ({ key, value }));

  const missingRequired = () =>
    allQuestions
      .filter((q) => (q.config.required as boolean) && (answers[q.key] === undefined || answers[q.key] === ""))
      .map((q) => q.prompt);

  return (
    <div className="space-y-5">
      {detail.sections.map((section) => (
        <section key={section.id} className="space-y-4 rounded-lg border bg-white p-4">
          <h3 className="font-semibold">{section.title}</h3>
          {section.questions.map((q) => (
            <QuestionField
              key={q.id}
              question={q}
              assessmentId={id}
              required={q.config.required as boolean}
              value={answers[q.key]}
              onChange={(v) => setAnswers((prev) => ({ ...prev, [q.key]: v }))}
            />
          ))}
        </section>
      ))}

      {detail.sections.length === 0 && (
        <p className="rounded-md bg-amber-50 p-3 text-sm text-amber-800">
          This assessment has no template questions; complete it to evaluate its saved responses.
        </p>
      )}

      {errors.length > 0 && (
        <div className="rounded-md bg-red-50 p-3 text-sm text-red-700">
          Please answer required questions: {errors.join(", ")}
        </div>
      )}
      {[save.error, complete.error].filter(Boolean).map((e, i) => (
        <p key={i} className="rounded-md bg-red-50 p-3 text-sm text-red-700">
          {(e as Error).message}
        </p>
      ))}

      <div className="flex gap-2">
        <button
          onClick={() => save.mutate(toPairs())}
          disabled={save.isPending}
          className="rounded-md border border-slate-900 px-4 py-2 text-sm font-medium text-slate-900 hover:bg-slate-100 disabled:opacity-50"
        >
          {save.isPending ? "Saving…" : save.isSuccess ? "Saved ✓" : "Save responses"}
        </button>
        <button
          onClick={async () => {
            const missing = missingRequired();
            setErrors(missing);
            if (missing.length) return;
            await save.mutateAsync(toPairs()); // responses saved before completing
            await complete.mutateAsync();
            qc.invalidateQueries({ queryKey: ["assessment", id] });
            qc.invalidateQueries({ queryKey: ["recommendations", id] });
          }}
          disabled={save.isPending || complete.isPending}
          className="rounded-md bg-slate-900 px-4 py-2 text-sm font-medium text-white hover:bg-slate-700 disabled:opacity-50"
        >
          {complete.isPending ? "Evaluating…" : "Save & complete assessment"}
        </button>
      </div>
    </div>
  );
}

function ReviewView({ id }: { id: string }) {
  const qc = useQueryClient();
  const recommendations = useRecommendations(id);
  const patch = usePatchRecommendation(id);
  const publish = usePublishReport(id);
  const report = useReport(id, true);

  const recs = recommendations.data ?? [];
  const allReviewed = recs.length > 0 && recs.every((r) => r.status === "approved" || r.status === "rejected");

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-end">
        <button
          onClick={() => publish.mutate(undefined, { onSuccess: () => qc.invalidateQueries({ queryKey: ["report", id] }) })}
          disabled={!allReviewed || publish.isPending}
          title={allReviewed ? "" : "Approve or reject every recommendation first"}
          className="rounded-md bg-slate-900 px-4 py-2 text-sm font-medium text-white hover:bg-slate-700 disabled:opacity-40"
        >
          {publish.isPending ? "Requesting…" : "Publish report"}
        </button>
      </div>

      {report.data?.status === "queued" && (
        <p className="rounded-md bg-amber-50 p-3 text-sm text-amber-800">Report rendering in the background…</p>
      )}
      {report.data?.status === "published" && report.data.pdf_url && (
        <a href={report.data.pdf_url} className="block rounded-md bg-green-50 p-3 text-sm text-green-800">
          Report published — view PDF
        </a>
      )}
      {[patch.error, publish.error].filter(Boolean).map((e, i) => (
        <p key={i} className="rounded-md bg-red-50 p-3 text-sm text-red-700">
          {(e as Error).message}
        </p>
      ))}

      {recommendations.isLoading && <p className="text-slate-500">Loading recommendations…</p>}
      {recs.length === 0 && !recommendations.isLoading && (
        <p className="text-slate-500">No findings were generated for this assessment.</p>
      )}
      <div className="space-y-3">
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
        <span className="ml-auto rounded bg-slate-100 px-2 py-0.5 text-xs font-medium text-slate-600">{rec.status}</span>
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
