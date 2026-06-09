import { Sparkles, Cpu } from "lucide-react";

import type { Recommendation } from "@/lib/schemas";
import { Card, CardContent } from "@/components/ui/card";
import { SeverityBadge } from "./SeverityBadge";

export function RecommendationCard({ rec }: { rec: Recommendation }) {
  const grounded = rec.provenance.source === "llm" && rec.provenance.grounding_passed;
  return (
    <Card>
      <CardContent className="space-y-3">
        <div className="flex items-center gap-2">
          <SeverityBadge severity={rec.severity} />
          <span className="font-mono text-xs text-muted-foreground">{rec.rule_code}</span>
          <span className="ml-auto inline-flex items-center gap-1 text-xs text-muted-foreground">
            {grounded ? <Sparkles className="size-3.5" /> : <Cpu className="size-3.5" />}
            {grounded ? "AI-enhanced · grounded" : "deterministic"}
          </span>
        </div>
        <h3 className="font-semibold">{rec.title}</h3>
        <dl className="space-y-1.5 text-sm">
          <Row label="Finding" value={rec.finding} />
          <Row label="Rationale" value={rec.rationale} />
          <Row label="Remediation" value={rec.remediation} />
        </dl>
      </CardContent>
    </Card>
  );
}

function Row({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <dt className="inline font-medium text-muted-foreground">{label}: </dt>
      <dd className="inline text-foreground/90">{value}</dd>
    </div>
  );
}
