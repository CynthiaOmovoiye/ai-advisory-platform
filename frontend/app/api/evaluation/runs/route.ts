import { listEvaluationRuns, triggerEvaluation } from "@/lib/api";
import { withIdentity } from "@/lib/bff";

export async function GET() {
  return withIdentity((identity) => listEvaluationRuns(identity));
}

export async function POST() {
  return withIdentity((identity) => triggerEvaluation(identity));
}
