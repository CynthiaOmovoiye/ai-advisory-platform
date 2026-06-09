import Link from "next/link";
import { Sparkles } from "lucide-react";

import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";

export function AuthShell({
  title,
  description,
  children,
  footer,
}: {
  title: string;
  description?: string;
  children: React.ReactNode;
  footer?: React.ReactNode;
}) {
  return (
    <div className="mx-auto flex min-h-[calc(100vh-8rem)] w-full max-w-sm flex-col justify-center px-4 py-10">
      <Link href="/" className="mb-6 flex items-center justify-center gap-2 font-semibold tracking-tight">
        <span className="grid size-7 place-items-center rounded-md bg-primary text-primary-foreground">
          <Sparkles className="size-4" />
        </span>
        AI Advisory
      </Link>
      <Card>
        <CardHeader>
          <CardTitle className="text-xl">{title}</CardTitle>
          {description && <CardDescription>{description}</CardDescription>}
        </CardHeader>
        <CardContent>{children}</CardContent>
      </Card>
      {footer && <div className="mt-4 text-center text-sm text-muted-foreground">{footer}</div>}
    </div>
  );
}
