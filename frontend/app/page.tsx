import Link from "next/link";
import { redirect } from "next/navigation";
import {
  ArrowRight,
  ShieldCheck,
  Workflow,
  Sparkles,
  FileCheck2,
  Building2,
  ListChecks,
} from "lucide-react";

import { buttonVariants } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { auth } from "@/lib/auth";

const FEATURES = [
  {
    icon: Workflow,
    title: "Deterministic rule engine",
    body: "Findings come from versioned, auditable rules — not a model's guess. Every result is reproducible.",
  },
  {
    icon: Sparkles,
    title: "AI that explains, never invents",
    body: "The LLM writes the narrative around each finding and is grounding-checked. It can't change what was found.",
  },
  {
    icon: ShieldCheck,
    title: "Multi-tenant by design",
    body: "Default-deny RBAC plus Postgres row-level security. An org only ever sees its own data.",
  },
  {
    icon: FileCheck2,
    title: "Traceable to the source",
    body: "Each recommendation links back to the rule, the prompt, and the model that produced it.",
  },
];

const STEPS = [
  { icon: ListChecks, title: "Answer the assessment", body: "Work through a consultant-authored template across readiness, security, data, and governance." },
  { icon: Workflow, title: "The engine evaluates", body: "Deterministic rules produce graded findings; the AI drafts a grounded explanation for each." },
  { icon: FileCheck2, title: "Review & publish", body: "A consultant approves every recommendation, then publishes a traceable report." },
];

export default async function Home() {
  const session = await auth();
  if (session?.user) redirect("/assessments");

  return (
    <div>
      {/* Hero */}
      <section className="relative overflow-hidden border-b">
        <div
          aria-hidden
          className="pointer-events-none absolute inset-0 -z-10 bg-[radial-gradient(60%_50%_at_50%_0%,color-mix(in_oklch,var(--primary)_14%,transparent),transparent)]"
        />
        <div className="mx-auto max-w-6xl px-4 py-20 sm:px-6 sm:py-28">
          <div className="mx-auto max-w-3xl text-center">
            <span className="inline-flex items-center gap-1.5 rounded-full border bg-card px-3 py-1 text-xs font-medium text-muted-foreground">
              <Building2 className="size-3.5" />
              AI readiness, advisory-grade
            </span>
            <h1 className="mt-6 text-4xl font-semibold tracking-tight text-balance sm:text-5xl">
              Assess your organization&apos;s readiness for AI — with findings you can defend.
            </h1>
            <p className="mt-5 text-lg text-muted-foreground text-pretty">
              A deterministic rule engine produces the findings; AI explains them. Every
              recommendation is traceable, grounded, and tenant-isolated.
            </p>
            <div className="mt-8 flex items-center justify-center gap-3">
              <Link href="/signup" className={buttonVariants({ size: "lg" })}>
                Get started <ArrowRight className="size-4" />
              </Link>
              <Link href="/login" className={buttonVariants({ variant: "outline", size: "lg" })}>
                Sign in
              </Link>
            </div>
          </div>
        </div>
      </section>

      {/* How it works */}
      <section className="mx-auto max-w-6xl px-4 py-16 sm:px-6">
        <h2 className="text-center text-2xl font-semibold tracking-tight">How it works</h2>
        <div className="mt-10 grid gap-6 md:grid-cols-3">
          {STEPS.map((s, i) => {
            const Icon = s.icon;
            return (
              <div key={s.title} className="relative rounded-xl border bg-card p-6">
                <span className="absolute right-4 top-4 text-5xl font-bold text-muted/60 tabular-nums">
                  {i + 1}
                </span>
                <span className="grid size-10 place-items-center rounded-lg bg-primary/10 text-primary">
                  <Icon className="size-5" />
                </span>
                <h3 className="mt-4 font-semibold">{s.title}</h3>
                <p className="mt-2 text-sm text-muted-foreground">{s.body}</p>
              </div>
            );
          })}
        </div>
      </section>

      {/* Features */}
      <section className="border-t bg-muted/30">
        <div className="mx-auto max-w-6xl px-4 py-16 sm:px-6">
          <h2 className="text-center text-2xl font-semibold tracking-tight">
            Built like infrastructure, not a demo
          </h2>
          <div className="mt-10 grid gap-5 sm:grid-cols-2">
            {FEATURES.map((f) => {
              const Icon = f.icon;
              return (
                <Card key={f.title}>
                  <CardHeader>
                    <span className="grid size-9 place-items-center rounded-lg bg-primary/10 text-primary">
                      <Icon className="size-5" />
                    </span>
                    <CardTitle className="mt-3">{f.title}</CardTitle>
                    <CardDescription>{f.body}</CardDescription>
                  </CardHeader>
                </Card>
              );
            })}
          </div>
        </div>
      </section>

      {/* CTA */}
      <section className="mx-auto max-w-6xl px-4 py-16 sm:px-6">
        <div className="rounded-2xl border bg-primary px-8 py-12 text-center text-primary-foreground">
          <h2 className="text-2xl font-semibold tracking-tight">Ready to run your first assessment?</h2>
          <p className="mx-auto mt-2 max-w-xl text-primary-foreground/80">
            Create an organization, invite your team, and produce a defensible AI-readiness report.
          </p>
          <div className="mt-6">
            <Link
              href="/signup"
              className={buttonVariants({ variant: "secondary", size: "lg" })}
            >
              Create your account <ArrowRight className="size-4" />
            </Link>
          </div>
        </div>
      </section>
    </div>
  );
}
