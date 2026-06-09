"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";
import { Plus, Trash2, Rocket } from "lucide-react";

import { PageContainer, PageHeader } from "@/components/PageHeader";
import { StatusBadge } from "@/components/SeverityBadge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { selectClass } from "@/lib/utils";
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
    <PageContainer>
      <PageHeader
        title="Assessment templates"
        description="Reusable, versioned assessment definitions. Publish one to start an assessment from it."
      />

      <Card className="p-0">
        <div className="divide-y">
          {(templates.data ?? []).map((t) => (
            <div key={t.id} className="flex items-center justify-between gap-4 px-4 py-3.5">
              <div className="min-w-0">
                <p className="truncate font-medium">{t.title}</p>
                <p className="mt-1 flex items-center gap-2 text-xs text-muted-foreground">
                  <span className="font-mono">{t.category}</span>
                  <span>·</span>
                  <span>{t.sections.reduce((n, s) => n + s.questions.length, 0)} questions</span>
                  <StatusBadge status={t.status} />
                </p>
              </div>
              <div className="flex shrink-0 gap-2">
                {t.status !== "published" && (
                  <Button variant="outline" size="sm" onClick={() => publish.mutate(t.id)}>
                    Publish
                  </Button>
                )}
                {t.status === "published" && (
                  <Button
                    size="sm"
                    onClick={() =>
                      start.mutate(t.id, {
                        onSuccess: (a) => router.push(`/assessments/${(a as { id: string }).id}`),
                      })
                    }
                  >
                    <Rocket className="size-4" /> Start
                  </Button>
                )}
              </div>
            </div>
          ))}
          {templates.data?.length === 0 && (
            <p className="px-4 py-10 text-center text-sm text-muted-foreground">No templates yet.</p>
          )}
        </div>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Author a new template</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="flex flex-wrap gap-3">
            <div className="flex-1 space-y-1.5">
              <Label htmlFor="t-title">Title</Label>
              <Input id="t-title" value={title} onChange={(e) => setTitle(e.target.value)} placeholder="AI Readiness — Baseline" />
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="t-cat">Category</Label>
              <select id="t-cat" value={category} onChange={(e) => setCategory(e.target.value)} className={selectClass}>
                {CATEGORIES.map((c) => (
                  <option key={c} value={c}>
                    {c}
                  </option>
                ))}
              </select>
            </div>
          </div>

          <div className="space-y-2">
            <Label className="text-xs uppercase tracking-wide text-muted-foreground">Questions</Label>
            {questions.map((q, i) => (
              <div key={i} className="flex flex-wrap items-center gap-2">
                <Input
                  value={q.key}
                  onChange={(e) => setQ(i, { key: e.target.value })}
                  placeholder="key (a-z0-9_)"
                  className="w-40"
                />
                <Input
                  value={q.prompt}
                  onChange={(e) => setQ(i, { prompt: e.target.value })}
                  placeholder="Question prompt"
                  className="flex-1"
                />
                <select value={q.type} onChange={(e) => setQ(i, { type: e.target.value })} className={`${selectClass} w-40`}>
                  {QUESTION_TYPES.map((t) => (
                    <option key={t} value={t}>
                      {t}
                    </option>
                  ))}
                </select>
                {questions.length > 1 && (
                  <Button
                    type="button"
                    variant="ghost"
                    size="icon"
                    onClick={() => setQuestions((qs) => qs.filter((_, j) => j !== i))}
                    aria-label="Remove question"
                  >
                    <Trash2 className="size-4" />
                  </Button>
                )}
              </div>
            ))}
            <Button
              type="button"
              variant="ghost"
              size="sm"
              onClick={() => setQuestions((qs) => [...qs, { key: "", prompt: "", type: "single_select" }])}
            >
              <Plus className="size-4" /> Add question
            </Button>
          </div>

          {create.isError && (
            <p className="rounded-md bg-destructive/10 p-3 text-sm text-destructive">
              {(create.error as Error).message}
            </p>
          )}

          <Button
            onClick={() =>
              create.mutate(
                {
                  category,
                  title,
                  sections: [{ title: "General", questions: questions.filter((q) => q.key && q.prompt) }],
                },
                {
                  onSuccess: () => {
                    setTitle("");
                    setQuestions([{ key: "", prompt: "", type: "single_select" }]);
                  },
                },
              )
            }
            disabled={create.isPending || !title}
          >
            {create.isPending ? "Creating…" : "Create template (draft)"}
          </Button>
        </CardContent>
      </Card>
    </PageContainer>
  );
}
