import type { Severity } from "@/lib/schemas";
import { cn } from "@/lib/utils";

const STYLES: Record<Severity, string> = {
  critical: "bg-destructive/10 text-destructive ring-destructive/20",
  high: "bg-orange-100 text-orange-700 ring-orange-600/20 dark:bg-orange-400/10 dark:text-orange-300",
  medium: "bg-amber-100 text-amber-800 ring-amber-600/20 dark:bg-amber-400/10 dark:text-amber-300",
  low: "bg-primary/10 text-primary ring-primary/20",
  info: "bg-muted text-muted-foreground ring-border",
};

export function SeverityBadge({ severity }: { severity: Severity }) {
  return (
    <span
      className={cn(
        "inline-flex items-center rounded-md px-2 py-0.5 text-xs font-medium uppercase tracking-wide ring-1 ring-inset",
        STYLES[severity],
      )}
    >
      {severity}
    </span>
  );
}

const STATUS_STYLES: Record<string, string> = {
  in_progress: "bg-amber-100 text-amber-800 ring-amber-600/20 dark:bg-amber-400/10 dark:text-amber-300",
  evaluating: "bg-primary/10 text-primary ring-primary/20",
  completed: "bg-primary/10 text-primary ring-primary/20",
  reviewed: "bg-success/10 text-success ring-success/20",
  approved: "bg-success/10 text-success ring-success/20",
  published: "bg-success/10 text-success ring-success/20",
  rejected: "bg-destructive/10 text-destructive ring-destructive/20",
  draft: "bg-muted text-muted-foreground ring-border",
  invited: "bg-amber-100 text-amber-800 ring-amber-600/20 dark:bg-amber-400/10 dark:text-amber-300",
  active: "bg-success/10 text-success ring-success/20",
  removed: "bg-muted text-muted-foreground ring-border",
  queued: "bg-amber-100 text-amber-800 ring-amber-600/20 dark:bg-amber-400/10 dark:text-amber-300",
  failed: "bg-destructive/10 text-destructive ring-destructive/20",
};

export function StatusBadge({ status }: { status: string }) {
  return (
    <span
      className={cn(
        "inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium ring-1 ring-inset",
        STATUS_STYLES[status] ?? "bg-muted text-muted-foreground ring-border",
      )}
    >
      {status.replace(/_/g, " ")}
    </span>
  );
}
