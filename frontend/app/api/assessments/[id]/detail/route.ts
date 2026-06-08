import { getAssessment } from "@/lib/api";
import { withIdentity } from "@/lib/bff";

export async function GET(_req: Request, { params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  return withIdentity((identity) => getAssessment(identity, id));
}
