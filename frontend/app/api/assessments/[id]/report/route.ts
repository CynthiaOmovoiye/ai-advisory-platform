import { publishReport } from "@/lib/api";
import { withIdentity } from "@/lib/bff";

// Publish a report (consultant/admin). Enforces the approval gate in the backend.
export async function POST(_req: Request, { params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  return withIdentity((identity) => publishReport(identity, id));
}
