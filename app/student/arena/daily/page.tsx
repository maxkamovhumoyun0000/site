import { StudentCompetitionRedirect } from "../../competition-redirect";

export default function StudentDailyArenaPage({
  searchParams,
}: {
  searchParams?: Record<string, string | string[] | undefined>;
}) {
  return <StudentCompetitionRedirect section="arena-daily" arenaMode="arena-daily" searchParams={searchParams} />;
}
