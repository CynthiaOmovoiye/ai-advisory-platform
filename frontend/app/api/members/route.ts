import { inviteMember, listMembers } from "@/lib/api";
import { withIdentity } from "@/lib/bff";

export async function GET() {
  return withIdentity((identity) => listMembers(identity));
}

export async function POST(req: Request) {
  const body = (await req.json()) as { email: string; role: "org_user" | "consultant" };
  return withIdentity((identity) => inviteMember(identity, body.email, body.role));
}
