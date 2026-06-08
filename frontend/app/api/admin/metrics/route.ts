import { getAdminMetrics } from "@/lib/api";
import { withIdentity } from "@/lib/bff";

export async function GET() {
  return withIdentity((identity) => getAdminMetrics(identity));
}
