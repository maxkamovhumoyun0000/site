import { ClientRedirect } from "../../../ui/client-redirect";

type SearchParamsInput = Promise<Record<string, string | string[] | undefined>> | Record<string, string | string[] | undefined>;

function readSingle(value: string | string[] | undefined, fallback = "") {
  if (Array.isArray(value)) return String(value[0] || fallback);
  return String(value || fallback);
}

export default async function LegacyStudentGrammarTopicPage({
  searchParams,
}: {
  searchParams: SearchParamsInput;
}) {
  const params = await Promise.resolve(searchParams);
  const topicId = readSingle(params.topic_id).trim();
  const subject = readSingle(params.subject, "English").trim() || "English";
  const level = readSingle(params.level, "A1").trim().toUpperCase() || "A1";

  if (!topicId) {
    return <ClientRedirect href={`/student/grammar?subject=${encodeURIComponent(subject)}&level=${encodeURIComponent(level)}`} />;
  }

  return <ClientRedirect href={`/student/grammar/${encodeURIComponent(topicId)}?subject=${encodeURIComponent(subject)}&level=${encodeURIComponent(level)}`} />;
}
