import { ClientRedirect } from "../../ui/client-redirect";

export default function StudentDailyPage({
  searchParams,
}: {
  searchParams?: Record<string, string | string[] | undefined>;
}) {
  const params = new URLSearchParams();
  params.set("role", "student");
  params.set("section", "daily-test");
  const subject = String(searchParams?.subject || "").trim();
  if (subject) params.set("subject", subject);
  return <ClientRedirect href={`/?${params.toString()}`} />;
}
