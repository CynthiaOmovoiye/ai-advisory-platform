import { patchRecommendation, type RecommendationPatch } from "@/lib/api";
import { withIdentity } from "@/lib/bff";

export async function PATCH(req: Request, { params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  const patch = (await req.json()) as RecommendationPatch;
  return withIdentity((identity) => patchRecommendation(identity, id, patch));
}
