import { removeMember } from "@/lib/api";
import { withIdentity } from "@/lib/bff";

export async function DELETE(_req: Request, { params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  return withIdentity((identity) => removeMember(identity, id));
}
