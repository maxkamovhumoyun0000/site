import { StudentCompetitionRedirect } from "../../competition-redirect";

export default function StudentGroupArenaPage({
  searchParams,
}: {
  searchParams?: Record<string, string | string[] | undefined>;
}) {
  return <StudentCompetitionRedirect section="arena-group" arenaMode="arena-group" searchParams={searchParams} />;
}
