"use client";

import { useAdminMetrics } from "@/lib/queries";

export default function AdminDashboard() {
  const metrics = useAdminMetrics();

  if (metrics.isLoading) return <p className="text-slate-500">Loading metrics…</p>;
  if (metrics.isError)
    return <p className="rounded-md bg-red-50 p-3 text-sm text-red-700">{(metrics.error as Error).message}</p>;

  const m = metrics.data!;
  const groundingPct =
    m.ai_usage.grounding_pass_rate != null ? `${Math.round(m.ai_usage.grounding_pass_rate * 100)}%` : "—";

  return (
    <div className="space-y-6">
      <h2 className="text-xl font-semibold">Admin Dashboard</h2>

      <div className="grid grid-cols-2 gap-4 md:grid-cols-4">
        <Stat label="Organizations" value={m.organizations} />
        <Stat label="Assessments" value={m.assessments_total} />
        <Stat label="Reports published" value={m.reports_published} />
        <Stat label="Recommendations" value={m.ai_usage.recommendations_total} />
      </div>

      <section className="rounded-lg border bg-white p-4">
        <h3 className="font-semibold">AI usage &amp; quality</h3>
        <dl className="mt-2 grid grid-cols-2 gap-2 text-sm md:grid-cols-3">
          <Item label="LLM-enhanced" value={String(m.ai_usage.by_source.llm ?? 0)} />
          <Item label="Deterministic fallback" value={String(m.ai_usage.by_source.fallback ?? 0)} />
          <Item label="Grounding pass rate" value={groundingPct} />
        </dl>
      </section>

      <section className="rounded-lg border bg-white p-4">
        <h3 className="font-semibold">Latest evaluation</h3>
        <dl className="mt-2 grid grid-cols-3 gap-2 text-sm">
          <Item label="Accuracy" value={fmt(m.evaluation.latest_accuracy)} />
          <Item label="Hallucination rate" value={fmt(m.evaluation.latest_hallucination_rate)} />
          <Item label="Status" value={m.evaluation.latest_status ?? "—"} />
        </dl>
      </section>
    </div>
  );
}

function fmt(v: number | null) {
  return v == null ? "—" : v.toFixed(3);
}

function Stat({ label, value }: { label: string; value: number }) {
  return (
    <div className="rounded-lg border bg-white p-4">
      <div className="text-2xl font-semibold">{value}</div>
      <div className="text-xs text-slate-500">{label}</div>
    </div>
  );
}

function Item({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <dt className="text-slate-500">{label}</dt>
      <dd className="font-medium">{value}</dd>
    </div>
  );
}
