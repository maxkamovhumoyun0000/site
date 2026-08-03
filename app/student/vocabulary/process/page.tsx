import { ClientRedirect } from "../../../ui/client-redirect";

export default function StudentVocabularyProcessPage({
  searchParams,
}: {
  searchParams?: Record<string, string | string[] | undefined>;
}) {
  const params = new URLSearchParams();
  params.set("role", "student");
  params.set("section", "vocabulary-process");
  const subject = String(searchParams?.subject || "").trim();
  if (subject) params.set("subject", subject);
  return <ClientRedirect href={`/?${params.toString()}`} />;
}
