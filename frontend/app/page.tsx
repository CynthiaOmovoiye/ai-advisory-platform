import Link from "next/link";

export default function Home() {
  return (
    <div className="space-y-4">
      <p className="text-slate-600">
        Assess your organization&apos;s readiness for AI adoption. A deterministic rule
        engine produces the findings; AI explains them. Every recommendation is traceable
        and grounded.
      </p>
      <Link
        href="/assessments"
        className="inline-flex rounded-md bg-slate-900 px-4 py-2 text-sm font-medium text-white hover:bg-slate-700"
      >
        View assessments
      </Link>
    </div>
  );
}
