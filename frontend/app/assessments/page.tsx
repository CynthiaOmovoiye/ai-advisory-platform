"use client";

import Link from "next/link";
import { ArrowRight, ClipboardList } from "lucide-react";

import { PageContainer, PageHeader } from "@/components/PageHeader";
import { StatusBadge } from "@/components/SeverityBadge";
import { buttonVariants } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { useAssessments } from "@/lib/queries";

export default function AssessmentsPage() {
  const assessments = useAssessments();
  const data = assessments.data ?? [];

  return (
    <PageContainer>
      <PageHeader
        title="Assessments"
        description="In-progress and completed AI-readiness assessments for your organization."
        action={
          <Link href="/templates" className={buttonVariants({ size: "sm" })}>
            Start from a template <ArrowRight className="size-4" />
          </Link>
        }
      />

      {assessments.isError && (
        <p className="rounded-md bg-destructive/10 p-3 text-sm text-destructive">
          {(assessments.error as Error).message}
        </p>
      )}

      {assessments.isLoading ? (
        <div className="space-y-2">
          {[0, 1, 2].map((i) => (
            <Skeleton key={i} className="h-16 w-full rounded-lg" />
          ))}
        </div>
      ) : data.length === 0 ? (
        <Card className="flex flex-col items-center gap-3 py-14 text-center">
          <span className="grid size-12 place-items-center rounded-full bg-muted text-muted-foreground">
            <ClipboardList className="size-6" />
          </span>
          <div>
            <p className="font-medium">No assessments yet</p>
            <p className="text-sm text-muted-foreground">Start one from a published template.</p>
          </div>
          <Link href="/templates" className={buttonVariants({ variant: "outline", size: "sm" })}>
            Browse templates
          </Link>
        </Card>
      ) : (
        <Card className="divide-y p-0">
          {data.map((a) => (
            <Link
              key={a.id}
              href={`/assessments/${a.id}`}
              className="flex items-center justify-between gap-4 px-4 py-3.5 transition-colors hover:bg-accent/40"
            >
              <div className="min-w-0">
                <p className="truncate font-medium">{a.template_name}</p>
                <div className="mt-1">
                  <StatusBadge status={a.status} />
                </div>
              </div>
              <span className="inline-flex items-center gap-1 text-sm font-medium text-primary">
                {a.status === "in_progress" ? "Continue" : "Open"}
                <ArrowRight className="size-4" />
              </span>
            </Link>
          ))}
        </Card>
      )}
    </PageContainer>
  );
}
