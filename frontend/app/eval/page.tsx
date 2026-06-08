"use client";

import { useEvaluationRuns, useTriggerEvaluation } from "@/lib/queries";

export default function EvalDashboard() {
  const runs = useEvaluationRuns();
  const trigger = useTriggerEvaluation();

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h2 className="text-xl font-semibold">Evaluation</h2>
        <button
          onClick={() => trigger.mutate()}
          disabled={trigger.isPending}
          className="rounded-md bg-slate-900 px-4 py-2 text-sm font-medium text-white hover:bg-slate-700 disabled:opacity-50"
        >
          {trigger.isPending ? "Running…" : "Run evaluation"}
        </button>
      </div>

      {trigger.isError && (
        <p className="rounded-md bg-red-50 p-3 text-sm text-red-700">{(trigger.error as Error).message}</p>
      )}

      <div className="overflow-hidden rounded-lg border bg-white">
        <table className="w-full text-sm">
          <thead className="bg-slate-50 text-left text-xs uppercase text-slate-500">
            <tr>
              <th className="px-4 py-2">Dataset</th>
              <th className="px-4 py-2">Model</th>
              <th className="px-4 py-2">Accuracy</th>
              <th className="px-4 py-2">Hallucination</th>
              <th className="px-4 py-2">Consistency</th>
              <th className="px-4 py-2">Status</th>
            </tr>
          </thead>
          <tbody className="divide-y">
            {(runs.data ?? []).map((r) => (
              <tr key={r.id}>
                <td className="px-4 py-2">{r.dataset_name}</td>
                <td className="px-4 py-2 text-slate-500">{r.model_id}</td>
                <td className="px-4 py-2">{r.accuracy.toFixed(3)}</td>
                <td className="px-4 py-2">{r.hallucination_rate.toFixed(3)}</td>
                <td className="px-4 py-2">{r.consistency.toFixed(3)}</td>
                <td className="px-4 py-2">
                  <span
                    className={
                      r.status === "completed"
                        ? "text-green-700"
                        : "font-medium text-red-700"
                    }
                  >
                    {r.status}
                  </span>
                </td>
              </tr>
            ))}
            {runs.data?.length === 0 && (
              <tr>
                <td colSpan={6} className="px-4 py-6 text-center text-slate-500">
                  No runs yet — trigger one to gate against regression.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
