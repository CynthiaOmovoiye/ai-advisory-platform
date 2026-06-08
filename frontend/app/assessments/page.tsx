import Link from "next/link";

// In the full system this lists the caller's assessments from the backend (tenant
// scoped). Shown here as a static demo entry pointing at the working detail view.
const DEMO_ASSESSMENTS = [
  { id: "assess-a", title: "AI Readiness", status: "completed" },
];

export default function AssessmentsPage() {
  return (
    <div className="space-y-4">
      <h2 className="text-xl font-semibold">Assessments</h2>
      <ul className="divide-y rounded-lg border bg-white">
        {DEMO_ASSESSMENTS.map((a) => (
          <li key={a.id} className="flex items-center justify-between px-4 py-3">
            <div>
              <p className="font-medium">{a.title}</p>
              <p className="text-xs text-slate-500">{a.status}</p>
            </div>
            <Link
              href={`/assessments/${a.id}`}
              className="text-sm font-medium text-blue-700 hover:underline"
            >
              Open →
            </Link>
          </li>
        ))}
      </ul>
    </div>
  );
}
