"use client";

import { useState } from "react";
import { Paperclip } from "lucide-react";

import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { cn, selectClass } from "@/lib/utils";

export interface Question {
  id: string;
  key: string;
  prompt: string;
  type: string;
  config: Record<string, unknown>;
}

function options(q: Question, fallback: unknown[]): unknown[] {
  const o = q.config.options;
  return Array.isArray(o) && o.length > 0 ? o : fallback;
}

function label(v: unknown): string {
  if (typeof v === "boolean") return v ? "Yes" : "No";
  return String(v);
}

/** Renders one dynamic question and reports its typed value back to the parent. */
export function QuestionField({
  question,
  value,
  onChange,
  assessmentId,
  required,
}: {
  question: Question;
  value: unknown;
  onChange: (v: unknown) => void;
  assessmentId: string;
  required?: boolean;
}) {
  return (
    <div className="space-y-2">
      <Label className="text-sm">
        {question.prompt}
        {required && <span className="text-destructive"> *</span>}
      </Label>

      {question.type === "text" && (
        <Input value={(value as string) ?? ""} onChange={(e) => onChange(e.target.value)} />
      )}

      {question.type === "long_text" && (
        <textarea
          className={cn(selectClass, "h-auto py-2")}
          rows={3}
          value={(value as string) ?? ""}
          onChange={(e) => onChange(e.target.value)}
        />
      )}

      {question.type === "number" && (
        <Input
          type="number"
          value={value === null || value === undefined ? "" : String(value)}
          onChange={(e) => onChange(e.target.value === "" ? null : Number(e.target.value))}
        />
      )}

      {question.type === "single_select" && (
        <select
          className={selectClass}
          value={value === undefined ? "" : JSON.stringify(value)}
          onChange={(e) => onChange(e.target.value === "" ? null : JSON.parse(e.target.value))}
        >
          <option value="">— select —</option>
          {options(question, [true, false]).map((opt, i) => (
            <option key={i} value={JSON.stringify(opt)}>
              {label(opt)}
            </option>
          ))}
        </select>
      )}

      {question.type === "multi_select" && (
        <div className="space-y-1.5">
          {options(question, []).map((opt, i) => {
            const arr = Array.isArray(value) ? (value as unknown[]) : [];
            const checked = arr.some((v) => JSON.stringify(v) === JSON.stringify(opt));
            return (
              <label key={i} className="flex items-center gap-2 text-sm">
                <input
                  type="checkbox"
                  className="size-4 rounded border-input accent-primary"
                  checked={checked}
                  onChange={(e) =>
                    onChange(
                      e.target.checked
                        ? [...arr, opt]
                        : arr.filter((v) => JSON.stringify(v) !== JSON.stringify(opt)),
                    )
                  }
                />
                {label(opt)}
              </label>
            );
          })}
        </div>
      )}

      {question.type === "file_upload" && (
        <FileUpload assessmentId={assessmentId} onUploaded={(id) => onChange(id)} value={value as string} />
      )}
    </div>
  );
}

function FileUpload({
  assessmentId,
  onUploaded,
  value,
}: {
  assessmentId: string;
  onUploaded: (documentId: string) => void;
  value?: string;
}) {
  const [status, setStatus] = useState<string | null>(value ? "uploaded" : null);
  const [error, setError] = useState<string | null>(null);

  return (
    <div className="text-sm">
      <label className="inline-flex cursor-pointer items-center gap-2 rounded-md border border-dashed px-3 py-2 text-muted-foreground transition-colors hover:bg-accent/50">
        <Paperclip className="size-4" />
        <span>Choose PDF or DOCX</span>
        <input
          type="file"
          accept=".pdf,.docx"
          className="hidden"
          onChange={async (e) => {
            const file = e.target.files?.[0];
            if (!file) return;
            setError(null);
            setStatus("uploading…");
            const form = new FormData();
            form.append("file", file);
            const res = await fetch(`/api/assessments/${assessmentId}/documents`, {
              method: "POST",
              body: form,
            });
            const body = await res.json().catch(() => null);
            if (!res.ok) {
              setStatus(null);
              setError(body?.message || body?.error || "Upload failed");
              return;
            }
            setStatus(`uploaded — scan: ${body.scan_status}`);
            onUploaded(body.id);
          }}
        />
      </label>
      {status && <span className="ml-2 text-muted-foreground">{status}</span>}
      {error && <p className="mt-1 text-destructive">{error}</p>}
      <p className="mt-1 text-xs text-muted-foreground">
        PDF or DOCX only. Not downloadable until scanned clean.
      </p>
    </div>
  );
}
