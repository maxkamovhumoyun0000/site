import { StudentCompetitionRedirect } from "../competition-redirect";

export default function StudentArenaPage({
  searchParams,
}: {
  searchParams?: Record<string, string | string[] | undefined>;
}) {
  return <StudentCompetitionRedirect section="arena" searchParams={searchParams} />;
}
