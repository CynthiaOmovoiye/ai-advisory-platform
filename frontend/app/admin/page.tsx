"use client";

import { Building2, ClipboardList, FileCheck2, Lightbulb } from "lucide-react";

import { PageContainer, PageHeader } from "@/components/PageHeader";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { useAdminMetrics } from "@/lib/queries";

export default function AdminDashboard() {
  const metrics = useAdminMetrics();

  return (
    <PageContainer>
      <PageHeader title="Admin dashboard" description="Platform-wide usage, AI quality, and cost telemetry." />

      {metrics.isError && (
        <p className="rounded-md bg-destructive/10 p-3 text-sm text-destructive">
          {(metrics.error as Error).message}
        </p>
      )}

      {metrics.isLoading || !metrics.data ? (
        <div className="grid grid-cols-2 gap-4 md:grid-cols-4">
          {[0, 1, 2, 3].map((i) => (
            <Skeleton key={i} className="h-24 rounded-xl" />
          ))}
        </div>
      ) : (
        <Loaded m={metrics.data} />
      )}
    </PageContainer>
  );
}

function Loaded({ m }: { m: NonNullable<ReturnType<typeof useAdminMetrics>["data"]> }) {
  const groundingPct =
    m.ai_usage.grounding_pass_rate != null ? `${Math.round(m.ai_usage.grounding_pass_rate * 100)}%` : "—";

  return (
    <>
      <div className="grid grid-cols-2 gap-4 md:grid-cols-4">
        <Stat icon={Building2} label="Organizations" value={m.organizations} />
        <Stat icon={ClipboardList} label="Assessments" value={m.assessments_total} />
        <Stat icon={FileCheck2} label="Reports published" value={m.reports_published} />
        <Stat icon={Lightbulb} label="Recommendations" value={m.ai_usage.recommendations_total} />
      </div>

      <div className="grid gap-4 md:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle>AI usage &amp; quality</CardTitle>
          </CardHeader>
          <CardContent>
            <dl className="grid grid-cols-2 gap-x-4 gap-y-3 text-sm sm:grid-cols-3">
              <Item label="LLM-enhanced" value={String(m.ai_usage.by_source.llm ?? 0)} />
              <Item label="Deterministic" value={String(m.ai_usage.by_source.fallback ?? 0)} />
              <Item label="Grounding pass" value={groundingPct} />
            </dl>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Latest evaluation</CardTitle>
          </CardHeader>
          <CardContent>
            <dl className="grid grid-cols-3 gap-x-4 gap-y-3 text-sm">
              <Item label="Accuracy" value={fmt(m.evaluation.latest_accuracy)} />
              <Item label="Hallucination" value={fmt(m.evaluation.latest_hallucination_rate)} />
              <Item label="Status" value={m.evaluation.latest_status ?? "—"} />
            </dl>
          </CardContent>
        </Card>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>LLM telemetry (captured)</CardTitle>
        </CardHeader>
        <CardContent>
          <dl className="grid grid-cols-2 gap-x-4 gap-y-3 text-sm sm:grid-cols-3 lg:grid-cols-5">
            <Item label="LLM calls" value={String(m.ai_usage.llm_calls)} />
            <Item label="Est. cost" value={`$${m.ai_usage.estimated_cost_usd.toFixed(4)}`} />
            <Item label="Avg latency" value={m.ai_usage.avg_latency_ms == null ? "—" : `${m.ai_usage.avg_latency_ms} ms`} />
            <Item label="Input tokens" value={m.ai_usage.total_input_tokens.toLocaleString()} />
            <Item label="Output tokens" value={m.ai_usage.total_output_tokens.toLocaleString()} />
          </dl>
        </CardContent>
      </Card>
    </>
  );
}

function fmt(v: number | null) {
  return v == null ? "—" : v.toFixed(3);
}

function Stat({
  icon: Icon,
  label,
  value,
}: {
  icon: React.ComponentType<{ className?: string }>;
  label: string;
  value: number;
}) {
  return (
    <Card>
      <CardContent className="flex items-center gap-3">
        <span className="grid size-10 place-items-center rounded-lg bg-primary/10 text-primary">
          <Icon className="size-5" />
        </span>
        <div>
          <div className="text-2xl font-semibold tabular-nums">{value}</div>
          <div className="text-xs text-muted-foreground">{label}</div>
        </div>
      </CardContent>
    </Card>
  );
}

function Item({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <dt className="text-muted-foreground">{label}</dt>
      <dd className="mt-0.5 font-medium tabular-nums">{value}</dd>
    </div>
  );
}
