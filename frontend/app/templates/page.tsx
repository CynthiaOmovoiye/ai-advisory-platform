"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";

import {
  useCreateTemplate,
  usePublishTemplate,
  useStartAssessment,
  useTemplates,
} from "@/lib/queries";

const CATEGORIES = [
  "ai_readiness",
  "data_maturity",
  "security",
  "governance",
  "compliance",
  "operations",
  "infrastructure",
];
const QUESTION_TYPES = ["single_select", "text", "long_text", "number", "multi_select", "file_upload"];

interface DraftQuestion {
  key: string;
  prompt: string;
  type: string;
}

export default function TemplatesPage() {
  const router = useRouter();
  const templates = useTemplates();
  const create = useCreateTemplate();
  const publish = usePublishTemplate();
  const start = useStartAssessment();

  const [title, setTitle] = useState("");
  const [category, setCategory] = useState("ai_readiness");
  const [questions, setQuestions] = useState<DraftQuestion[]>([
    { key: "", prompt: "", type: "single_select" },
  ]);

  const setQ = (i: number, patch: Partial<DraftQuestion>) =>
    setQuestions((qs) => qs.map((q, j) => (j === i ? { ...q, ...patch } : q)));

  return (
    <div className="space-y-8">
      <section className="space-y-3">
        <h2 className="text-xl font-semibold">Assessment Templates</h2>
        <ul className="divide-y rounded-lg border bg-white">
          {(templates.data ?? []).map((t) => (
            <li key={t.id} className="flex items-center justify-between px-4 py-3">
              <div>
                <p className="font-medium">{t.title}</p>
                <p className="text-xs text-slate-500">
                  {t.category} · {t.sections.reduce((n, s) => n + s.questions.length, 0)} questions ·{" "}
                  <span className={t.status === "published" ? "text-green-700" : "text-amber-700"}>
                    {t.status}
                  </span>
                </p>
              </div>
              <div className="flex gap-2">
                {t.status !== "published" && (
                  <button
                    onClick={() => publish.mutate(t.id)}
                    className="rounded-md border px-3 py-1 text-xs font-medium hover:bg-slate-50"
                  >
                    Publish
                  </button>
                )}
                {t.status === "published" && (
                  <button
                    onClick={() =>
                      start.mutate(t.id, {
                        onSuccess: (a: any) => router.push(`/assessments/${a.id}`),
                      })
                    }
                    className="rounded-md bg-slate-900 px-3 py-1 text-xs font-medium text-white hover:bg-slate-700"
                  >
                    Start assessment
                  </button>
                )}
              </div>
            </li>
          ))}
          {templates.data?.length === 0 && (
            <li className="px-4 py-6 text-center text-sm text-slate-500">No templates yet.</li>
          )}
        </ul>
      </section>

      <section className="space-y-3 rounded-lg border bg-white p-4">
        <h3 className="font-semibold">Author a new template</h3>
        <div className="flex flex-wrap gap-2">
          <input
            value={title}
            onChange={(e) => setTitle(e.target.value)}
            placeholder="Template title"
            className="flex-1 rounded-md border px-3 py-2 text-sm"
          />
          <select
            value={category}
            onChange={(e) => setCategory(e.target.value)}
            className="rounded-md border px-3 py-2 text-sm"
          >
            {CATEGORIES.map((c) => (
              <option key={c} value={c}>
                {c}
              </option>
            ))}
          </select>
        </div>

        <p className="text-xs font-medium uppercase text-slate-500">Questions</p>
        {questions.map((q, i) => (
          <div key={i} className="flex flex-wrap gap-2">
            <input
              value={q.key}
              onChange={(e) => setQ(i, { key: e.target.value })}
              placeholder="key (a-z0-9_)"
              className="w-40 rounded-md border px-3 py-2 text-sm"
            />
            <input
              value={q.prompt}
              onChange={(e) => setQ(i, { prompt: e.target.value })}
              placeholder="Question prompt"
              className="flex-1 rounded-md border px-3 py-2 text-sm"
            />
            <select
              value={q.type}
              onChange={(e) => setQ(i, { type: e.target.value })}
              className="rounded-md border px-3 py-2 text-sm"
            >
              {QUESTION_TYPES.map((t) => (
                <option key={t} value={t}>
                  {t}
                </option>
              ))}
            </select>
          </div>
        ))}
        <button
          onClick={() => setQuestions((qs) => [...qs, { key: "", prompt: "", type: "single_select" }])}
          className="text-sm font-medium text-blue-700 hover:underline"
        >
          + Add question
        </button>

        {create.isError && (
          <p className="rounded-md bg-red-50 p-3 text-sm text-red-700">{(create.error as Error).message}</p>
        )}

        <button
          onClick={() =>
            create.mutate(
              {
                category,
                title,
                sections: [{ title: "General", questions: questions.filter((q) => q.key && q.prompt) }],
              },
              { onSuccess: () => { setTitle(""); setQuestions([{ key: "", prompt: "", type: "single_select" }]); } },
            )
          }
          disabled={create.isPending || !title}
          className="rounded-md bg-slate-900 px-4 py-2 text-sm font-medium text-white hover:bg-slate-700 disabled:opacity-50"
        >
          {create.isPending ? "Creating…" : "Create template (draft)"}
        </button>
      </section>
    </div>
  );
}
