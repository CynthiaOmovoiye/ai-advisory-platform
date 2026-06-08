import { createTemplate, listTemplates, type TemplateInput } from "@/lib/api";
import { withIdentity } from "@/lib/bff";

export async function GET() {
  return withIdentity((identity) => listTemplates(identity));
}

export async function POST(req: Request) {
  const body = (await req.json()) as TemplateInput;
  return withIdentity((identity) => createTemplate(identity, body));
}
