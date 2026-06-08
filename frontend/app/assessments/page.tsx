"use client";

import Link from "next/link";

import { useAssessments } from "@/lib/queries";

const STATUS_STYLES: Record<string, string> = {
  in_progress: "text-amber-700",
  completed: "text-blue-700",
  evaluating: "text-blue-700",
  reviewed: "text-green-700",
};

export default function AssessmentsPage() {
  const assessments = useAssessments();

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h2 className="text-xl font-semibold">Assessments</h2>
        <Link href="/templates" className="text-sm font-medium text-blue-700 hover:underline">
          Start one from a template →
        </Link>
      </div>

      {assessments.isLoading && <p className="text-slate-500">Loading…</p>}
      {assessments.isError && (
        <p className="rounded-md bg-red-50 p-3 text-sm text-red-700">
          {(assessments.error as Error).message}
        </p>
      )}

      <ul className="divide-y rounded-lg border bg-white">
        {(assessments.data ?? []).map((a) => (
          <li key={a.id} className="flex items-center justify-between px-4 py-3">
            <div>
              <p className="font-medium">{a.template_name}</p>
              <p className="text-xs">
                <span className={STATUS_STYLES[a.status] ?? "text-slate-500"}>{a.status}</span>
              </p>
            </div>
            <Link
              href={`/assessments/${a.id}`}
              className="text-sm font-medium text-blue-700 hover:underline"
            >
              {a.status === "in_progress" ? "Continue →" : "Open →"}
            </Link>
          </li>
        ))}
        {assessments.data?.length === 0 && (
          <li className="px-4 py-6 text-center text-sm text-slate-500">
            No assessments yet — start one from a published template.
          </li>
        )}
      </ul>
    </div>
  );
}
