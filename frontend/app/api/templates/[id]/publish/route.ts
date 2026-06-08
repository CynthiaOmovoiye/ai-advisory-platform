import { publishTemplate } from "@/lib/api";
import { withIdentity } from "@/lib/bff";

export async function POST(_req: Request, { params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  return withIdentity((identity) => publishTemplate(identity, id));
}
