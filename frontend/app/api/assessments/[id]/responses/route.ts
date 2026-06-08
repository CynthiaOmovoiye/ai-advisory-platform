import { saveResponses } from "@/lib/api";
import { withIdentity } from "@/lib/bff";

export async function PUT(req: Request, { params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  const body = (await req.json()) as { responses: { key: string; value: unknown }[] };
  return withIdentity(async (identity) => {
    await saveResponses(identity, id, body.responses);
    return { ok: true };
  });
}
