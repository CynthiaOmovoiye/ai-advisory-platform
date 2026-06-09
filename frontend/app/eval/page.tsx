"use client";

import { Play } from "lucide-react";

import { PageContainer, PageHeader } from "@/components/PageHeader";
import { StatusBadge } from "@/components/SeverityBadge";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { useEvaluationRuns, useTriggerEvaluation } from "@/lib/queries";

export default function EvalDashboard() {
  const runs = useEvaluationRuns();
  const trigger = useTriggerEvaluation();

  return (
    <PageContainer>
      <PageHeader
        title="Evaluation"
        description="Regression-test AI output quality against a gold dataset."
        action={
          <Button onClick={() => trigger.mutate()} disabled={trigger.isPending}>
            <Play className="size-4" />
            {trigger.isPending ? "Running…" : "Run evaluation"}
          </Button>
        }
      />

      {trigger.isError && (
        <p className="rounded-md bg-destructive/10 p-3 text-sm text-destructive">
          {(trigger.error as Error).message}
        </p>
      )}

      <Card className="overflow-x-auto p-0">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b text-left text-xs uppercase tracking-wide text-muted-foreground">
              <th className="px-4 py-2.5 font-medium">Dataset</th>
              <th className="px-4 py-2.5 font-medium">Model</th>
              <th className="px-4 py-2.5 font-medium">Accuracy</th>
              <th className="px-4 py-2.5 font-medium">Hallucination</th>
              <th className="px-4 py-2.5 font-medium">Consistency</th>
              <th className="px-4 py-2.5 font-medium">Status</th>
            </tr>
          </thead>
          <tbody className="divide-y">
            {(runs.data ?? []).map((r) => (
              <tr key={r.id} className="hover:bg-accent/30">
                <td className="px-4 py-3 font-medium">{r.dataset_name}</td>
                <td className="px-4 py-3 font-mono text-xs text-muted-foreground">{r.model_id}</td>
                <td className="px-4 py-3 tabular-nums">{r.accuracy.toFixed(3)}</td>
                <td className="px-4 py-3 tabular-nums">{r.hallucination_rate.toFixed(3)}</td>
                <td className="px-4 py-3 tabular-nums">{r.consistency.toFixed(3)}</td>
                <td className="px-4 py-3">
                  <StatusBadge status={r.status} />
                </td>
              </tr>
            ))}
            {runs.data?.length === 0 && (
              <tr>
                <td colSpan={6} className="px-4 py-10 text-center text-muted-foreground">
                  No runs yet — trigger one to gate against regression.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </Card>
    </PageContainer>
  );
}
