import { getReport, publishReport } from "@/lib/api";
import { withIdentity } from "@/lib/bff";

// Enqueue a report render (consultant/admin). Enforces the approval gate; returns 202.
export async function POST(_req: Request, { params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  return withIdentity((identity) => publishReport(identity, id));
}

// Poll the report's current status (queued -> published).
export async function GET(_req: Request, { params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  return withIdentity((identity) => getReport(identity, id));
}
