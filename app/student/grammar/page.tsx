import { ClientRedirect } from "../../ui/client-redirect";

export default function StudentGrammarPage({
  searchParams,
}: {
  searchParams?: Record<string, string | string[] | undefined>;
}) {
  const params = new URLSearchParams();
  params.set("role", "student");
  params.set("section", "grammar");
  const subject = String(searchParams?.subject || "").trim();
  const level = String(searchParams?.level || "").trim();
  if (subject) params.set("subject", subject);
  if (level) params.set("level", level);
  return <ClientRedirect href={`/?${params.toString()}`} />;
}
