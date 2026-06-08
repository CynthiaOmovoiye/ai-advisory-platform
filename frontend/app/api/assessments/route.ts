import { createAssessment } from "@/lib/api";
import { withIdentity } from "@/lib/bff";

export async function POST(req: Request) {
  const { template_id } = (await req.json()) as { template_id: string };
  return withIdentity((identity) => createAssessment(identity, template_id));
}
