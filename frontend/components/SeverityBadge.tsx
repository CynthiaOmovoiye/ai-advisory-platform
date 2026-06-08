import type { Severity } from "@/lib/schemas";

const STYLES: Record<Severity, string> = {
  critical: "bg-red-100 text-red-800 ring-red-600/20",
  high: "bg-orange-100 text-orange-800 ring-orange-600/20",
  medium: "bg-amber-100 text-amber-800 ring-amber-600/20",
  low: "bg-blue-100 text-blue-800 ring-blue-600/20",
  info: "bg-slate-100 text-slate-700 ring-slate-500/20",
};

export function SeverityBadge({ severity }: { severity: Severity }) {
  return (
    <span
      className={`inline-flex items-center rounded-md px-2 py-0.5 text-xs font-medium uppercase ring-1 ring-inset ${STYLES[severity]}`}
    >
      {severity}
    </span>
  );
}
