import type { Recommendation } from "@/lib/schemas";

import { SeverityBadge } from "./SeverityBadge";

export function RecommendationCard({ rec }: { rec: Recommendation }) {
  return (
    <article className="rounded-lg border bg-white p-4 shadow-sm">
      <div className="flex items-center gap-2">
        <SeverityBadge severity={rec.severity} />
        <span className="text-xs text-slate-500">{rec.rule_code}</span>
        {/* Provenance — shows whether the narrative is LLM-grounded or a deterministic fallback */}
        <span className="ml-auto text-xs text-slate-400">
          {rec.provenance.source === "llm" && rec.provenance.grounding_passed
            ? "AI-enhanced ✓ grounded"
            : "deterministic"}
        </span>
      </div>
      <h3 className="mt-2 font-semibold">{rec.title}</h3>
      <dl className="mt-2 space-y-1 text-sm text-slate-700">
        <div>
          <dt className="inline font-medium text-slate-500">Finding: </dt>
          <dd className="inline">{rec.finding}</dd>
        </div>
        <div>
          <dt className="inline font-medium text-slate-500">Rationale: </dt>
          <dd className="inline">{rec.rationale}</dd>
        </div>
        <div>
          <dt className="inline font-medium text-slate-500">Remediation: </dt>
          <dd className="inline">{rec.remediation}</dd>
        </div>
      </dl>
    </article>
  );
}
