"use client";

import { useQueryClient } from "@tanstack/react-query";
import { use, useState } from "react";
import { Check, X, FileDown, Loader2 } from "lucide-react";

import { PageContainer, PageHeader } from "@/components/PageHeader";
import { QuestionField } from "@/components/QuestionField";
import { SeverityBadge, StatusBadge } from "@/components/SeverityBadge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
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

  return (
    <PageContainer>
      {detail.isLoading ? (
        <Skeleton className="h-40 w-full rounded-xl" />
      ) : detail.isError ? (
        <p className="rounded-md bg-destructive/10 p-3 text-sm text-destructive">
          {(detail.error as Error).message}
        </p>
      ) : (
        <>
          <PageHeader
            title={detail.data!.template_name}
            action={<StatusBadge status={detail.data!.status} />}
          />
          {detail.data!.status === "in_progress" ? (
            <AnswerForm id={id} detail={detail.data!} />
          ) : (
            <ReviewView id={id} />
          )}
        </>
      )}
    </PageContainer>
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
        <Card key={section.id}>
          <CardHeader>
            <CardTitle>{section.title}</CardTitle>
          </CardHeader>
          <CardContent className="space-y-5">
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
          </CardContent>
        </Card>
      ))}

      {detail.sections.length === 0 && (
        <p className="rounded-md bg-amber-100/60 p-3 text-sm text-amber-800 dark:bg-amber-400/10 dark:text-amber-300">
          This assessment has no template questions; complete it to evaluate its saved responses.
        </p>
      )}

      {errors.length > 0 && (
        <div className="rounded-md bg-destructive/10 p-3 text-sm text-destructive">
          Please answer required questions: {errors.join(", ")}
        </div>
      )}
      {[save.error, complete.error].filter(Boolean).map((e, i) => (
        <p key={i} className="rounded-md bg-destructive/10 p-3 text-sm text-destructive">
          {(e as Error).message}
        </p>
      ))}

      <div className="flex flex-wrap gap-2">
        <Button variant="outline" onClick={() => save.mutate(toPairs())} disabled={save.isPending}>
          {save.isPending ? "Saving…" : save.isSuccess ? "Saved ✓" : "Save responses"}
        </Button>
        <Button
          onClick={async () => {
            const missing = missingRequired();
            setErrors(missing);
            if (missing.length) return;
            await save.mutateAsync(toPairs());
            await complete.mutateAsync();
            qc.invalidateQueries({ queryKey: ["assessment", id] });
            qc.invalidateQueries({ queryKey: ["recommendations", id] });
          }}
          disabled={save.isPending || complete.isPending}
        >
          {complete.isPending ? "Evaluating…" : "Save & complete assessment"}
        </Button>
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
  const reviewed = recs.filter((r) => r.status === "approved" || r.status === "rejected").length;
  const allReviewed = recs.length > 0 && reviewed === recs.length;

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <p className="text-sm text-muted-foreground">
          {recs.length > 0 ? `${reviewed} of ${recs.length} reviewed` : "Findings from the rule engine"}
        </p>
        <Button
          onClick={() =>
            publish.mutate(undefined, { onSuccess: () => qc.invalidateQueries({ queryKey: ["report", id] }) })
          }
          disabled={!allReviewed || publish.isPending}
          title={allReviewed ? "" : "Approve or reject every recommendation first"}
        >
          {publish.isPending ? "Requesting…" : "Publish report"}
        </Button>
      </div>

      {report.data?.status === "queued" && (
        <p className="flex items-center gap-2 rounded-md bg-amber-100/60 p-3 text-sm text-amber-800 dark:bg-amber-400/10 dark:text-amber-300">
          <Loader2 className="size-4 animate-spin" /> Report rendering in the background…
        </p>
      )}
      {report.data?.status === "published" && report.data.pdf_url && (
        <a
          href={report.data.pdf_url}
          className="flex items-center gap-2 rounded-md bg-success/10 p-3 text-sm font-medium text-success"
        >
          <FileDown className="size-4" /> Report published — view PDF
        </a>
      )}
      {[patch.error, publish.error].filter(Boolean).map((e, i) => (
        <p key={i} className="rounded-md bg-destructive/10 p-3 text-sm text-destructive">
          {(e as Error).message}
        </p>
      ))}

      {recommendations.isLoading && <Skeleton className="h-32 w-full rounded-xl" />}
      {recs.length === 0 && !recommendations.isLoading && (
        <Card className="py-10 text-center text-sm text-muted-foreground">
          No findings were generated for this assessment.
        </Card>
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
    <Card>
      <CardContent className="space-y-3">
        <div className="flex items-center gap-2">
          <SeverityBadge severity={rec.severity} />
          <span className="font-mono text-xs text-muted-foreground">{rec.rule_code}</span>
          <span className="ml-auto">
            <StatusBadge status={rec.status} />
          </span>
        </div>
        <h3 className="font-semibold">{rec.title}</h3>
        <p className="text-sm">
          <span className="font-medium text-muted-foreground">Rationale: </span>
          {rec.rationale}
        </p>
        <p className="text-sm">
          <span className="font-medium text-muted-foreground">Remediation: </span>
          {rec.remediation}
        </p>
        <div className="flex gap-2 pt-1">
          <Button
            size="sm"
            onClick={onApprove}
            disabled={busy || rec.status === "approved"}
            className="bg-success text-white hover:bg-success/90"
          >
            <Check className="size-4" /> Approve
          </Button>
          <Button size="sm" variant="destructive" onClick={onReject} disabled={busy || rec.status === "rejected"}>
            <X className="size-4" /> Reject
          </Button>
        </div>
      </CardContent>
    </Card>
  );
}
